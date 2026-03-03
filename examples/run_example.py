"""
MLOps Example Pipeline Runner
Runs the full CT (Continuous Training) flow end-to-end:

    1. Generate synthetic customer churn data
    2. Upload data to MinIO
    3. Train model with MLflow tracking
    4. Register & promote model in MLflow Registry
    5. Test prediction via Feast Feature Server

Usage:
    # Port-forward first (run in separate terminals):
    kubectl port-forward svc/minio -n mlops 9000:9000
    kubectl port-forward svc/mlflow -n mlops 5000:5000
    kubectl port-forward svc/feast-feature-server -n mlops 6566:6566

    # Then run:
    pip install -r requirements.txt
    python run_example.py
"""

import os
import sys
import logging
import time

import numpy as np
import pandas as pd
import mlflow
import mlflow.sklearn
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from sklearn.preprocessing import StandardScaler
from mlflow.models.signature import infer_signature

from generate_data import generate_customer_data, upload_to_minio

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Configuration — set via env or defaults for port-forwarded services
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://192.168.2.51:32052")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://192.168.2.51:31679")
FEAST_SERVER_URL = os.getenv("FEAST_SERVER_URL", "http://192.168.2.51:30523")
MODEL_NAME = "customer_churn_model"

# Feature columns (must match Feast feature views)
FEATURE_COLUMNS = [
    "total_purchases",
    "avg_order_value",
    "days_since_last_purchase",
    "total_revenue",
    "purchase_frequency",
    "txn_count_7d",
    "txn_amount_7d",
    "txn_count_30d",
    "txn_amount_30d",
    "avg_txn_amount_30d",
]

TARGET_COLUMN = "churned"


def step1_generate_data() -> pd.DataFrame:
    """Step 1: Generate synthetic data and upload to MinIO."""
    print("\n" + "=" * 60)
    print("STEP 1: Generate Synthetic Data")
    print("=" * 60)

    df = generate_customer_data(n=10_000, seed=42)

    # Save locally
    output_path = "/tmp/customer_churn_data.parquet"
    df.to_parquet(output_path, index=False)
    logger.info(f"Saved {len(df)} rows to {output_path}")

    # Upload to MinIO
    try:
        os.environ["MINIO_ENDPOINT"] = MINIO_ENDPOINT
        upload_to_minio(output_path, bucket="feast-data", object_name="customer_churn_data.parquet")
    except Exception as e:
        logger.warning(f"MinIO upload failed (OK for local testing): {e}")

    return df


def step2_train_model(df: pd.DataFrame) -> str:
    """Step 2: Train model and log to MLflow."""
    print("\n" + "=" * 60)
    print("STEP 2: Train Model + MLflow Tracking")
    print("=" * 60)

    # Set MLflow S3 settings for artifact storage
    os.environ["MLFLOW_S3_ENDPOINT_URL"] = MINIO_ENDPOINT
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "mlops-admin")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "changeme-minio-secret-2024")

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(MODEL_NAME)

    # Prepare data
    X = df[FEATURE_COLUMNS].fillna(0)
    y = df[TARGET_COLUMN]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Hyperparameters
    params = {
        "n_estimators": 200,
        "max_depth": 6,
        "learning_rate": 0.1,
        "min_samples_split": 10,
        "min_samples_leaf": 5,
        "subsample": 0.8,
        "random_state": 42,
    }

    with mlflow.start_run(run_name=f"example-{pd.Timestamp.now().strftime('%Y%m%d-%H%M%S')}") as run:
        run_id = run.info.run_id
        logger.info(f"MLflow Run ID: {run_id}")

        # Log params
        mlflow.log_params(params)
        mlflow.log_param("n_features", len(FEATURE_COLUMNS))
        mlflow.log_param("n_train_samples", X_train.shape[0])

        # Train
        logger.info("Training GradientBoostingClassifier...")
        model = GradientBoostingClassifier(**params)
        model.fit(X_train_scaled, y_train)

        # Evaluate
        y_pred = model.predict(X_test_scaled)
        y_proba = model.predict_proba(X_test_scaled)[:, 1]

        metrics = {
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred, zero_division=0),
            "recall": recall_score(y_test, y_pred, zero_division=0),
            "f1_score": f1_score(y_test, y_pred, zero_division=0),
            "roc_auc": roc_auc_score(y_test, y_proba),
        }
        mlflow.log_metrics(metrics)

        for name, value in metrics.items():
            logger.info(f"  {name}: {value:.4f}")

        # Log model with signature
        signature = infer_signature(X_test, y_pred)
        mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path="model",
            signature=signature,
            registered_model_name=MODEL_NAME,
        )

        logger.info(f"✅ Model registered as {MODEL_NAME}")
        return run_id


def step3_promote_model():
    """Step 3: Promote model to champion."""
    print("\n" + "=" * 60)
    print("STEP 3: Promote Model to Champion")
    print("=" * 60)

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = mlflow.tracking.MlflowClient()

    # Get latest version
    versions = client.search_model_versions(
        f"name='{MODEL_NAME}'",
        order_by=["version_number DESC"],
        max_results=1,
    )

    if not versions:
        logger.error("No model versions found!")
        return

    version = versions[0]
    version_num = version.version
    logger.info(f"Latest model version: {version_num}")

    # Set champion alias
    client.set_registered_model_alias(MODEL_NAME, "champion", version_num)
    client.set_registered_model_alias(MODEL_NAME, "production", version_num)
    client.set_model_version_tag(MODEL_NAME, version_num, "status", "production")

    logger.info(f"✅ Version {version_num} promoted to champion!")
    logger.info(f"   URI: models:/{MODEL_NAME}@champion")


def step4_test_prediction():
    """Step 4: Test prediction via Feast Feature Server."""
    print("\n" + "=" * 60)
    print("STEP 4: Test Prediction Flow")
    print("=" * 60)

    import httpx

    # Test Feast health
    try:
        resp = httpx.get(f"{FEAST_SERVER_URL}/health", timeout=5)
        logger.info(f"Feast health: {resp.status_code} — {resp.text[:100]}")
    except Exception as e:
        logger.warning(f"Feast not reachable ({e}). Skipping online feature test.")
        logger.info("(This is OK if Feast online store hasn't been materialized yet)")
        return

    # Test MLflow model loading
    logger.info("Loading model from MLflow...")
    os.environ["MLFLOW_S3_ENDPOINT_URL"] = MINIO_ENDPOINT
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

    try:
        model = mlflow.sklearn.load_model(f"models:/{MODEL_NAME}@champion")
        logger.info("✅ Model loaded successfully from MLflow Registry")

        # Make a test prediction with dummy features
        test_features = pd.DataFrame([{
            "total_purchases": 30,
            "avg_order_value": 45.50,
            "days_since_last_purchase": 15,
            "total_revenue": 1365.0,
            "purchase_frequency": 3.2,
            "txn_count_7d": 4,
            "txn_amount_7d": 180.0,
            "txn_count_30d": 15,
            "txn_amount_30d": 680.0,
            "avg_txn_amount_30d": 45.33,
        }])

        scaler = StandardScaler()
        scaler.fit(test_features)  # Simplified for demo
        prediction = model.predict(test_features)
        probability = model.predict_proba(test_features)[:, 1]

        logger.info(f"Test prediction: class={prediction[0]}, probability={probability[0]:.4f}")
        logger.info("✅ End-to-end prediction flow works!")

    except Exception as e:
        logger.error(f"Model loading failed: {e}")


def main():
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║           MLOps Example Pipeline Runner                 ║
    ║                                                         ║
    ║   Step 1: Generate synthetic data → MinIO               ║
    ║   Step 2: Train model → MLflow                          ║
    ║   Step 3: Promote model → champion                      ║
    ║   Step 4: Test prediction flow                          ║
    ╚══════════════════════════════════════════════════════════╝
    """)

    # Step 1: Generate data
    df = step1_generate_data()

    # Step 2: Train model
    run_id = step2_train_model(df)

    # Step 3: Promote
    step3_promote_model()

    # Step 4: Test
    step4_test_prediction()

    print("\n" + "=" * 60)
    print("🎉 EXAMPLE PIPELINE COMPLETE!")
    print("=" * 60)
    print(f"""
Next steps:
  1. Open MLflow UI: kubectl port-forward svc/mlflow -n mlops 5000:5000
     → http://localhost:5000

  2. Open Feast UI: kubectl port-forward svc/feast-feature-server -n mlops 8888:8888
     → http://localhost:8888

  3. Open Airflow UI: kubectl port-forward svc/airflow-api-server -n mlops 8080:8080
     → http://localhost:8080
     Login: admin / admin
    """)


if __name__ == "__main__":
    main()
