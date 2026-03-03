"""
Fetch Data Module
Retrieves historical training data from Feast Offline Store.

Usage: python -m ml.fetch_data
"""

import os
import logging
from datetime import datetime, timedelta

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Output path shared between pipeline steps (within the Pod's shared volume)
DATA_OUTPUT_PATH = os.getenv("DATA_OUTPUT_PATH", "/tmp/training_data.parquet")


def fetch_training_data() -> pd.DataFrame:
    """Fetch historical features from Feast for model training."""
    from feast import FeatureStore

    logger.info("Initializing Feast FeatureStore...")
    fs = FeatureStore(repo_path=os.getenv("FEAST_FEATURE_STORE_YAML", "/opt/feast"))

    # Define the entity DataFrame (which customers to fetch features for)
    # In production, this would come from your data warehouse or a query
    entity_df = pd.DataFrame(
        {
            "customer_id": list(range(1, 10001)),  # Example: 10k customers
            "event_timestamp": [datetime.now() - timedelta(days=1)] * 10000,
        }
    )

    logger.info(f"Fetching features for {len(entity_df)} entities...")

    # Get historical features for training
    training_df = fs.get_historical_features(
        entity_df=entity_df,
        features=[
            "customer_features:total_purchases",
            "customer_features:avg_order_value",
            "customer_features:days_since_last_purchase",
            "customer_features:total_revenue",
            "customer_features:purchase_frequency",
            "transaction_features:txn_count_7d",
            "transaction_features:txn_amount_7d",
            "transaction_features:txn_count_30d",
            "transaction_features:txn_amount_30d",
            "transaction_features:avg_txn_amount_30d",
        ],
    ).to_df()

    logger.info(f"Retrieved training data: {training_df.shape[0]} rows, {training_df.shape[1]} columns")
    logger.info(f"Columns: {list(training_df.columns)}")

    # Save to shared volume for next pipeline step
    training_df.to_parquet(DATA_OUTPUT_PATH, index=False)
    logger.info(f"Saved training data to {DATA_OUTPUT_PATH}")

    # Upload to S3 for sharing between pipeline steps (each step is a separate Pod)
    from ml.s3_storage import upload_artifact
    upload_artifact(DATA_OUTPUT_PATH, "pipeline/training_data.parquet")

    return training_df


if __name__ == "__main__":
    fetch_training_data()
