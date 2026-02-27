"""
Model Promotion Module — MLflow Aliases (no deprecated stages)
Promotes the challenger model to Production using MLflow model aliases.

Usage: python -m ml.promote
"""

import os
import sys
import logging

import mlflow
from mlflow.tracking import MlflowClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MODEL_NAME = os.getenv("MODEL_NAME", "customer_churn_model")


def promote_model():
    """
    Promote the latest model version to Production using MLflow aliases.
    - Sets alias 'champion' on the new model version
    - Removes 'champion' alias from the old version (if any)
    """
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI"))
    client = MlflowClient()

    # Get the latest model version
    versions = client.search_model_versions(
        f"name='{MODEL_NAME}'",
        order_by=["version_number DESC"],
        max_results=1,
    )
    if not versions:
        logger.error(f"No model versions found for '{MODEL_NAME}'")
        sys.exit(1)

    latest_version = versions[0]
    version_num = latest_version.version

    # Check if the evaluation step marked it for promotion
    mv = client.get_model_version(MODEL_NAME, version_num)
    tags = mv.tags or {}

    evaluation_result = tags.get("evaluation", "")
    if evaluation_result not in ("promoted", "promoted_first_model"):
        logger.info(f"Model version {version_num} was NOT marked for promotion (evaluation={evaluation_result})")
        logger.info("Skipping promotion. Pipeline complete.")
        return

    logger.info(f"Promoting model version {version_num}...")

    # Get current champion (if any) via alias
    try:
        current_champion = client.get_model_version_by_alias(MODEL_NAME, "champion")
        if current_champion.version != version_num:
            logger.info(f"Previous champion: version {current_champion.version}")
            # Tag old champion
            client.set_model_version_tag(MODEL_NAME, current_champion.version, "status", "archived")
    except Exception:
        logger.info("No existing champion found. This is the first promotion.")

    # Set the 'champion' alias on the new version
    client.set_registered_model_alias(MODEL_NAME, "champion", version_num)
    # Also set a 'production' alias for backward compatibility
    client.set_registered_model_alias(MODEL_NAME, "production", version_num)

    # Tag the version
    client.set_model_version_tag(MODEL_NAME, version_num, "status", "production")

    logger.info(f"✅ Model version {version_num} is now the champion!")
    logger.info(f"   Model URI: models:/{MODEL_NAME}@champion")


if __name__ == "__main__":
    promote_model()
