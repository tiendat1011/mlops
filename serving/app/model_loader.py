"""
Model Loader
Loads the Production model from MLflow Model Registry at startup.
"""

import os
import logging

import mlflow

logger = logging.getLogger(__name__)

MODEL_NAME = os.getenv("MODEL_NAME", "customer_churn_model")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow.mlops.svc.cluster.local:5000")


class ModelLoader:
    """Manages loading and caching the ML model from MLflow."""

    def __init__(self):
        self.model = None
        self.model_version = "none"
        self.model_name = MODEL_NAME

    def load(self):
        """Load the Production model from MLflow Registry."""
        logger.info(f"Connecting to MLflow at {MLFLOW_TRACKING_URI}")
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

        model_uri = f"models:/{MODEL_NAME}/Production"
        logger.info(f"Loading model: {model_uri}")

        try:
            self.model = mlflow.sklearn.load_model(model_uri)
            # Get version info
            client = mlflow.tracking.MlflowClient()
            versions = client.get_latest_versions(MODEL_NAME, stages=["Production"])
            if versions:
                self.model_version = versions[0].version
            logger.info(f"✅ Model loaded: {MODEL_NAME} v{self.model_version}")
        except Exception as e:
            logger.error(f"❌ Failed to load model: {e}")
            raise

    def predict(self, features):
        """Run prediction on prepared features."""
        if self.model is None:
            raise RuntimeError("Model not loaded")
        return self.model.predict(features), self.model.predict_proba(features)

    @property
    def is_loaded(self) -> bool:
        return self.model is not None


# Singleton instance
model_loader = ModelLoader()
