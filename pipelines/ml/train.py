"""
Model Training Module
Trains a model and logs everything to MLflow (params, metrics, artifacts).

Usage: python -m ml.train
"""

import os
import logging

import mlflow
import mlflow.sklearn
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATA_INPUT_PATH = os.getenv("DATA_OUTPUT_PATH", "/tmp/training_data.parquet")
MODEL_NAME = os.getenv("MODEL_NAME", "customer_churn_model")

# Hyperparameters (could be injected via Airflow Variables or env)
HYPERPARAMS = {
    "n_estimators": int(os.getenv("N_ESTIMATORS", "200")),
    "max_depth": int(os.getenv("MAX_DEPTH", "6")),
    "learning_rate": float(os.getenv("LEARNING_RATE", "0.1")),
    "min_samples_split": int(os.getenv("MIN_SAMPLES_SPLIT", "10")),
    "min_samples_leaf": int(os.getenv("MIN_SAMPLES_LEAF", "5")),
    "subsample": float(os.getenv("SUBSAMPLE", "0.8")),
    "random_state": 42,
}

# Features used for training (exclude entity keys and timestamps)
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

# Target column (must be present in the dataset)
TARGET_COLUMN = os.getenv("TARGET_COLUMN", "churned")


def train_model():
    """Train the model and log to MLflow."""
    logger.info(f"Loading training data from {DATA_INPUT_PATH}...")
    df = pd.read_parquet(DATA_INPUT_PATH)

    # Prepare features and target
    available_features = [c for c in FEATURE_COLUMNS if c in df.columns]
    logger.info(f"Using features: {available_features}")

    X = df[available_features].fillna(0)
    y = df[TARGET_COLUMN] if TARGET_COLUMN in df.columns else (df["days_since_last_purchase"] > 90).astype(int)

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    logger.info(f"Training set: {X_train.shape[0]} rows, Test set: {X_test.shape[0]} rows")
    logger.info(f"Positive class ratio: {y_train.mean():.2%}")

    # Configure MLflow
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI"))
    mlflow.set_experiment(MODEL_NAME)

    with mlflow.start_run(run_name=f"train-{pd.Timestamp.now().strftime('%Y%m%d-%H%M%S')}") as run:
        logger.info(f"MLflow Run ID: {run.info.run_id}")

        # Log hyperparameters
        mlflow.log_params(HYPERPARAMS)
        mlflow.log_param("n_features", len(available_features))
        mlflow.log_param("n_train_samples", X_train.shape[0])
        mlflow.log_param("n_test_samples", X_test.shape[0])
        mlflow.log_param("positive_class_ratio", round(y_train.mean(), 4))

        # Train
        logger.info("Training GradientBoostingClassifier...")
        model = GradientBoostingClassifier(**HYPERPARAMS)
        model.fit(X_train_scaled, y_train)

        # Predict
        y_pred = model.predict(X_test_scaled)
        y_proba = model.predict_proba(X_test_scaled)[:, 1]

        # Calculate metrics
        metrics = {
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred, zero_division=0),
            "recall": recall_score(y_test, y_pred, zero_division=0),
            "f1_score": f1_score(y_test, y_pred, zero_division=0),
            "roc_auc": roc_auc_score(y_test, y_proba),
        }

        # Log metrics
        mlflow.log_metrics(metrics)
        for name, value in metrics.items():
            logger.info(f"  {name}: {value:.4f}")

        # Log feature importances
        importance_df = pd.DataFrame(
            {"feature": available_features, "importance": model.feature_importances_}
        ).sort_values("importance", ascending=False)
        logger.info(f"Feature importances:\n{importance_df.to_string(index=False)}")
        importance_df.to_csv("/tmp/feature_importances.csv", index=False)
        mlflow.log_artifact("/tmp/feature_importances.csv")

        # Log model with signature
        from mlflow.models.signature import infer_signature

        signature = infer_signature(X_test, y_pred)
        mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path="model",
            signature=signature,
            registered_model_name=MODEL_NAME,
        )

        logger.info(f"✅ Model trained and logged to MLflow (Run: {run.info.run_id})")
        logger.info(f"   Registered as: {MODEL_NAME}")

        return run.info.run_id, metrics


if __name__ == "__main__":
    train_model()
