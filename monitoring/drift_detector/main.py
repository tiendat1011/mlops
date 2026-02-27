"""
Data Drift Detector
Uses Evidently AI to compute data drift between training data and production predictions.
Exports drift metrics to Prometheus for Grafana alerting.

Runs as a CronJob or Airflow DAG task.
"""

import os
import logging
import time
from datetime import datetime, timedelta

import pandas as pd
import numpy as np
from prometheus_client import Gauge, start_http_server, CollectorRegistry

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Configuration
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow.mlops.svc.cluster.local:5000")
MODEL_NAME = os.getenv("MODEL_NAME", "customer_churn_model")
DRIFT_THRESHOLD = float(os.getenv("DRIFT_THRESHOLD", "0.2"))
METRICS_PORT = int(os.getenv("METRICS_PORT", "9090"))
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "3600"))  # 1 hour

# Prometheus metrics
registry = CollectorRegistry()
DRIFT_SCORE = Gauge(
    "model_data_drift_score",
    "Overall data drift score (0-1, higher = more drift)",
    ["model_name"],
    registry=registry,
)
DRIFT_DETECTED = Gauge(
    "model_data_drift_detected",
    "Whether drift exceeds threshold (1=yes, 0=no)",
    ["model_name"],
    registry=registry,
)
FEATURE_DRIFT = Gauge(
    "model_feature_drift_score",
    "Per-feature drift score",
    ["model_name", "feature_name"],
    registry=registry,
)
LAST_CHECK_TIMESTAMP = Gauge(
    "model_drift_last_check_timestamp",
    "Unix timestamp of last drift check",
    ["model_name"],
    registry=registry,
)


def load_reference_data() -> pd.DataFrame:
    """Load training data as reference distribution."""
    # In production, load from MLflow artifacts or MinIO
    import mlflow

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = mlflow.tracking.MlflowClient()

    # Get the production model's training run
    versions = client.get_latest_versions(MODEL_NAME, stages=["Production"])
    if not versions:
        raise RuntimeError("No Production model found")

    run = client.get_run(versions[0].run_id)
    # Try to load feature importances (which tells us what features were used)
    logger.info(f"Reference data from run: {run.info.run_id}")

    # Placeholder: In production, reference data would be stored as an artifact
    # For now, generate synthetic reference data matching the training distribution
    np.random.seed(42)
    n = 1000
    return pd.DataFrame({
        "total_purchases": np.random.randint(0, 100, n),
        "avg_order_value": np.random.uniform(10, 500, n),
        "days_since_last_purchase": np.random.randint(0, 365, n),
        "total_revenue": np.random.uniform(100, 10000, n),
        "purchase_frequency": np.random.uniform(0, 10, n),
        "txn_count_7d": np.random.randint(0, 20, n),
        "txn_amount_7d": np.random.uniform(0, 1000, n),
        "txn_count_30d": np.random.randint(0, 50, n),
        "txn_amount_30d": np.random.uniform(0, 5000, n),
        "avg_txn_amount_30d": np.random.uniform(0, 200, n),
    })


def load_production_data() -> pd.DataFrame:
    """Load recent production prediction data."""
    # In production: query from a logging table, Kafka topic, or MinIO
    # Placeholder: generate slightly drifted data
    np.random.seed(int(time.time()) % 100000)
    n = 500
    return pd.DataFrame({
        "total_purchases": np.random.randint(0, 120, n),  # Slight drift
        "avg_order_value": np.random.uniform(15, 550, n),
        "days_since_last_purchase": np.random.randint(0, 400, n),
        "total_revenue": np.random.uniform(100, 12000, n),
        "purchase_frequency": np.random.uniform(0, 12, n),
        "txn_count_7d": np.random.randint(0, 25, n),
        "txn_amount_7d": np.random.uniform(0, 1200, n),
        "txn_count_30d": np.random.randint(0, 60, n),
        "txn_amount_30d": np.random.uniform(0, 6000, n),
        "avg_txn_amount_30d": np.random.uniform(0, 250, n),
    })


def compute_drift(reference: pd.DataFrame, production: pd.DataFrame) -> dict:
    """Compute data drift using Evidently AI."""
    try:
        from evidently.report import Report
        from evidently.metric_preset import DataDriftPreset

        report = Report(metrics=[DataDriftPreset()])
        report.run(reference_data=reference, current_data=production)

        result = report.as_dict()
        metrics = result["metrics"][0]["result"]

        drift_info = {
            "overall_drift_score": metrics.get("share_of_drifted_columns", 0),
            "drift_detected": metrics.get("dataset_drift", False),
            "n_drifted_columns": metrics.get("number_of_drifted_columns", 0),
            "n_total_columns": metrics.get("number_of_columns", 0),
            "per_feature": {},
        }

        # Extract per-feature drift
        drift_by_columns = metrics.get("drift_by_columns", {})
        for feature_name, feature_info in drift_by_columns.items():
            drift_info["per_feature"][feature_name] = {
                "drift_score": feature_info.get("drift_score", 0),
                "drift_detected": feature_info.get("drift_detected", False),
                "stattest_name": feature_info.get("stattest_name", "unknown"),
            }

        return drift_info

    except ImportError:
        logger.warning("Evidently not installed. Using simple KS-test fallback.")
        from scipy import stats

        drift_info = {"overall_drift_score": 0, "drift_detected": False, "per_feature": {}}
        drifted = 0
        for col in reference.columns:
            if col in production.columns:
                stat, p_value = stats.ks_2samp(reference[col].dropna(), production[col].dropna())
                is_drifted = p_value < 0.05
                drift_info["per_feature"][col] = {
                    "drift_score": round(stat, 4),
                    "drift_detected": is_drifted,
                }
                if is_drifted:
                    drifted += 1

        drift_info["overall_drift_score"] = drifted / max(len(reference.columns), 1)
        drift_info["drift_detected"] = drift_info["overall_drift_score"] > DRIFT_THRESHOLD
        return drift_info


def update_metrics(drift_info: dict):
    """Update Prometheus metrics with drift results."""
    score = drift_info["overall_drift_score"]
    DRIFT_SCORE.labels(model_name=MODEL_NAME).set(score)
    DRIFT_DETECTED.labels(model_name=MODEL_NAME).set(1 if drift_info["drift_detected"] else 0)
    LAST_CHECK_TIMESTAMP.labels(model_name=MODEL_NAME).set(time.time())

    for feature_name, info in drift_info.get("per_feature", {}).items():
        FEATURE_DRIFT.labels(model_name=MODEL_NAME, feature_name=feature_name).set(
            info.get("drift_score", 0)
        )

    logger.info(f"Drift score: {score:.4f}, Detected: {drift_info['drift_detected']}")


def trigger_retrain():
    """Trigger Airflow DAG for retraining via API."""
    import httpx

    airflow_url = os.getenv("AIRFLOW_API_URL", "http://airflow-webserver.mlops.svc.cluster.local:8080")
    dag_id = "training_pipeline"

    try:
        response = httpx.post(
            f"{airflow_url}/api/v1/dags/{dag_id}/dagRuns",
            json={
                "conf": {"retrain_reason": "data_drift_detected"},
            },
            auth=("admin", os.getenv("AIRFLOW_PASSWORD", "admin")),
            timeout=30,
        )
        response.raise_for_status()
        logger.info(f"✅ Triggered retraining DAG: {response.json()}")
    except Exception as e:
        logger.error(f"❌ Failed to trigger retrain: {e}")


def run_drift_check():
    """Run a single drift check cycle."""
    logger.info("Running drift check...")
    reference = load_reference_data()
    production = load_production_data()
    drift_info = compute_drift(reference, production)
    update_metrics(drift_info)

    if drift_info["drift_detected"]:
        logger.warning(f"⚠️  Data drift detected! Score: {drift_info['overall_drift_score']:.4f}")
        trigger_retrain()


def main():
    """Main loop: start Prometheus server and run periodic drift checks."""
    logger.info(f"Starting drift detector on port {METRICS_PORT}")
    start_http_server(METRICS_PORT, registry=registry)

    while True:
        try:
            run_drift_check()
        except Exception as e:
            logger.error(f"Drift check failed: {e}")
        logger.info(f"Next check in {CHECK_INTERVAL_SECONDS}s...")
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
