"""
Model Promotion Module
Promotes the challenger model to Production if evaluation passed.

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
    Promote the latest model version to Production if it was marked as 'promoted' by evaluation.
    Archives the previous Production model.
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
    tags = {tag.key: tag.value for tag in latest_version.tags} if hasattr(latest_version, 'tags') else {}
    # Also try fetching tags via API
    mv = client.get_model_version(MODEL_NAME, version_num)
    tags = mv.tags or {}

    evaluation_result = tags.get("evaluation", "")
    if evaluation_result not in ("promoted", "promoted_first_model"):
        logger.info(f"Model version {version_num} was NOT marked for promotion (evaluation={evaluation_result})")
        logger.info("Skipping promotion. Pipeline complete.")
        return

    logger.info(f"Promoting model version {version_num} to Production...")

    # Archive current Production models
    current_production = client.get_latest_versions(MODEL_NAME, stages=["Production"])
    for prod_version in current_production:
        logger.info(f"Archiving previous Production model: version {prod_version.version}")
        client.transition_model_version_stage(
            name=MODEL_NAME,
            version=prod_version.version,
            stage="Archived",
            archive_existing_versions=False,
        )

    # Promote challenger to Production
    client.transition_model_version_stage(
        name=MODEL_NAME,
        version=version_num,
        stage="Production",
        archive_existing_versions=False,
    )

    # Also set alias for MLflow 2.x+ clients
    try:
        client.set_registered_model_alias(MODEL_NAME, "champion", version_num)
    except Exception as e:
        logger.warning(f"Could not set alias (MLflow might not support aliases): {e}")

    logger.info(f"✅ Model version {version_num} is now Production!")
    logger.info(f"   Model URI: models:/{MODEL_NAME}/Production")


if __name__ == "__main__":
    promote_model()
