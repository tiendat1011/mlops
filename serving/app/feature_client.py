"""
Feast Feature Client — HTTP API
Retrieves online features from the centralized Feast Feature Server via HTTP.
No direct Redis or Feast SDK dependency needed in the serving app.
"""

import os
import logging
from typing import Optional

import httpx
import pandas as pd

logger = logging.getLogger(__name__)

FEAST_SERVER_URL = os.getenv(
    "FEAST_SERVER_URL",
    "http://feast-feature-server.mlops.svc.cluster.local:6566",
)

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
    """Fetches online features from Feast Feature Server via HTTP API."""

    def __init__(self):
        self._client: Optional[httpx.Client] = None

    def connect(self):
        """Initialize HTTP client to Feast Feature Server."""
        logger.info(f"Connecting to Feast Feature Server at {FEAST_SERVER_URL}")
        self._client = httpx.Client(base_url=FEAST_SERVER_URL, timeout=10.0)

        # Health check
        try:
            resp = self._client.get("/health")
            resp.raise_for_status()
            logger.info("✅ Feast Feature Server is healthy")
        except Exception as e:
            logger.warning(f"⚠️ Feast health check failed: {e}")

    def get_online_features(self, customer_id: int) -> dict:
        """Retrieve online features for a single customer via HTTP API."""
        if self._client is None:
            raise RuntimeError("Feast client not connected")

        payload = {
            "features": ONLINE_FEATURES,
            "entities": {"customer_id": [customer_id]},
        }

        resp = self._client.post("/get-online-features", json=payload)
        resp.raise_for_status()
        data = resp.json()

        # Parse response: {"metadata": {...}, "results": [{"values": [...], "statuses": [...], "event_timestamps": [...]}]}
        results = data.get("results", [])
        metadata = data.get("metadata", {})
        feature_names = metadata.get("feature_names", [])

        # Build a flat dict of feature_name → value
        features = {}
        for i, name in enumerate(feature_names):
            if i < len(results):
                values = results[i].get("values", [])
                features[name] = values[0] if values else None

        logger.debug(f"Online features for customer {customer_id}: {features}")
        return features

    def get_feature_vector(self, customer_id: int) -> pd.DataFrame:
        """Get features as a DataFrame ready for model prediction."""
        features = self.get_online_features(customer_id)
        # Remove entity key
        features.pop("customer_id", None)
        return pd.DataFrame([features])


# Singleton instance
feature_client = FeatureClient()
