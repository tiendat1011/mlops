"""
Feast Online Feature Client
Retrieves realtime features from Feast Online Store (Redis) for prediction.
"""

import os
import logging
from datetime import datetime

import pandas as pd
from feast import FeatureStore

logger = logging.getLogger(__name__)

FEAST_REPO_PATH = os.getenv("FEAST_FEATURE_STORE_YAML", "/opt/feast")

# Features to retrieve for prediction
ONLINE_FEATURES = [
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
]


class FeatureClient:
    """Manages connection to Feast Online Store."""

    def __init__(self):
        self.fs = None

    def connect(self):
        """Initialize Feast FeatureStore connection."""
        logger.info(f"Connecting to Feast repo at {FEAST_REPO_PATH}")
        self.fs = FeatureStore(repo_path=FEAST_REPO_PATH)
        logger.info("✅ Feast FeatureStore connected")

    def get_online_features(self, customer_id: int) -> dict:
        """Retrieve online features for a single customer."""
        if self.fs is None:
            raise RuntimeError("Feast not connected")

        entity_rows = [{"customer_id": customer_id}]

        features = self.fs.get_online_features(
            features=ONLINE_FEATURES,
            entity_rows=entity_rows,
        ).to_dict()

        # Convert to single-row dict (remove list wrapping)
        result = {k: v[0] if v else None for k, v in features.items()}
        logger.debug(f"Online features for customer {customer_id}: {result}")
        return result

    def get_feature_vector(self, customer_id: int) -> pd.DataFrame:
        """Get features as a DataFrame ready for model prediction."""
        features = self.get_online_features(customer_id)
        # Remove entity key
        features.pop("customer_id", None)
        return pd.DataFrame([features])


# Singleton instance
feature_client = FeatureClient()
