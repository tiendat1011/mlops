"""
Model Evaluation Module
Compares the newly trained model against the current champion (Production) model.

Usage: python -m ml.evaluate
"""

import os
import sys
import logging

import mlflow
from mlflow.tracking import MlflowClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MODEL_NAME = os.getenv("MODEL_NAME", "customer_churn_model")
# Primary metric to compare models
PRIMARY_METRIC = os.getenv("PRIMARY_METRIC", "f1_score")
# Minimum improvement required to promote (e.g., 0.01 = 1% better)
MIN_IMPROVEMENT = float(os.getenv("MIN_IMPROVEMENT", "0.01"))


def get_champion_metrics(client: MlflowClient) -> dict | None:
    """Get metrics from the current Production (champion) model."""
    try:
        # Search for model versions with alias "champion" or stage "Production"
        latest_versions = client.get_latest_versions(MODEL_NAME, stages=["Production"])
        if not latest_versions:
            # Try using aliases (MLflow 2.x+)
            try:
                mv = client.get_model_version_by_alias(MODEL_NAME, "champion")
                run = client.get_run(mv.run_id)
                return run.data.metrics
            except Exception:
                logger.info("No champion model found. First-time training.")
                return None

        champion_version = latest_versions[0]
        run = client.get_run(champion_version.run_id)
        logger.info(f"Champion model: version {champion_version.version}, run {champion_version.run_id}")
        return run.data.metrics

    except Exception as e:
        logger.warning(f"Could not retrieve champion metrics: {e}")
        return None


def get_challenger_metrics(client: MlflowClient) -> tuple[dict, str]:
    """Get metrics from the most recently trained (challenger) model."""
    # Get the latest model version (just registered by training step)
    versions = client.search_model_versions(
        f"name='{MODEL_NAME}'",
        order_by=["version_number DESC"],
        max_results=1,
    )
    if not versions:
        raise RuntimeError(f"No model versions found for '{MODEL_NAME}'")

    challenger = versions[0]
    run = client.get_run(challenger.run_id)
    logger.info(f"Challenger model: version {challenger.version}, run {challenger.run_id}")
    return run.data.metrics, challenger.version


def evaluate_model() -> bool:
    """
    Compare challenger vs champion model.
    Returns True if challenger should be promoted.
    """
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI"))
    client = MlflowClient()

    # Get metrics
    challenger_metrics, challenger_version = get_challenger_metrics(client)
    champion_metrics = get_champion_metrics(client)

    challenger_score = challenger_metrics.get(PRIMARY_METRIC, 0)
    logger.info(f"Challenger {PRIMARY_METRIC}: {challenger_score:.4f}")

    if champion_metrics is None:
        logger.info("No champion exists — challenger wins by default.")
        # Store decision as a tag on the model version
        client.set_model_version_tag(MODEL_NAME, challenger_version, "evaluation", "promoted_first_model")
        return True

    champion_score = champion_metrics.get(PRIMARY_METRIC, 0)
    improvement = challenger_score - champion_score
    logger.info(f"Champion {PRIMARY_METRIC}: {champion_score:.4f}")
    logger.info(f"Improvement: {improvement:+.4f} (threshold: {MIN_IMPROVEMENT})")

    # Compare all metrics for logging
    logger.info("── Metric Comparison ──")
    all_metric_keys = set(challenger_metrics.keys()) | set(champion_metrics.keys())
    for key in sorted(all_metric_keys):
        c_val = challenger_metrics.get(key, "N/A")
        p_val = champion_metrics.get(key, "N/A")
        marker = ""
        if isinstance(c_val, (int, float)) and isinstance(p_val, (int, float)):
            diff = c_val - p_val
            marker = f" ({diff:+.4f})" if diff != 0 else " (=)"
        logger.info(f"  {key}: champion={p_val}, challenger={c_val}{marker}")

    if improvement >= MIN_IMPROVEMENT:
        logger.info(f"✅ Challenger WINS by {improvement:.4f} ≥ {MIN_IMPROVEMENT}")
        client.set_model_version_tag(MODEL_NAME, challenger_version, "evaluation", "promoted")
        return True
    else:
        logger.info(f"❌ Challenger does NOT meet threshold (improvement: {improvement:.4f} < {MIN_IMPROVEMENT})")
        client.set_model_version_tag(MODEL_NAME, challenger_version, "evaluation", "rejected")
        return False


if __name__ == "__main__":
    should_promote = evaluate_model()
    if not should_promote:
        logger.info("Model will NOT be promoted. Exiting with status 0 (pipeline continues).")
    sys.exit(0)
