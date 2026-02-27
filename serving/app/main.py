"""
Model Serving API
FastAPI application that serves predictions using MLflow model + Feast features.

Endpoints:
  - POST /predict     — Get prediction for a customer
  - GET  /health      — Health check
  - GET  /metrics     — Prometheus metrics
"""

import os
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Histogram, generate_latest
from starlette.responses import Response

from app.schemas import PredictionRequest, PredictionResponse, HealthResponse
from app.model_loader import model_loader
from app.feature_client import feature_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Prometheus Metrics ──────────────────────────────────
PREDICTION_COUNT = Counter(
    "model_predictions_total",
    "Total number of predictions made",
    ["model_name", "model_version"],
)
PREDICTION_LATENCY = Histogram(
    "model_prediction_latency_seconds",
    "Prediction latency in seconds",
    ["model_name"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)
PREDICTION_ERRORS = Counter(
    "model_prediction_errors_total",
    "Total prediction errors",
    ["model_name", "error_type"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model and connect to Feast on startup."""
    logger.info("Starting up Model Serving API...")
    try:
        model_loader.load()
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        # Continue running so health check reports model_loaded=false

    try:
        feature_client.connect()
    except Exception as e:
        logger.error(f"Failed to connect to Feast: {e}")

    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="MLOps Model Serving API",
    description="Customer churn prediction API backed by MLflow + Feast",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy" if model_loader.is_loaded else "degraded",
        model_loaded=model_loader.is_loaded,
        model_name=model_loader.model_name,
        model_version=model_loader.model_version,
    )


@app.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest):
    """
    Get churn prediction for a customer.
    1. Fetches realtime features from Feast Online Store (Redis)
    2. Runs prediction using the Production model from MLflow
    """
    start_time = time.time()

    if not model_loader.is_loaded:
        PREDICTION_ERRORS.labels(
            model_name=model_loader.model_name, error_type="model_not_loaded"
        ).inc()
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        # Step 1: Get features from Feast
        feature_vector = feature_client.get_feature_vector(request.customer_id)
        features_dict = feature_vector.to_dict(orient="records")[0]

        # Step 2: Predict
        predictions, probabilities = model_loader.predict(feature_vector)
        prediction = int(predictions[0])
        probability = float(probabilities[0][1])  # Probability of class 1 (churn)

        # Record metrics
        latency = time.time() - start_time
        PREDICTION_COUNT.labels(
            model_name=model_loader.model_name,
            model_version=model_loader.model_version,
        ).inc()
        PREDICTION_LATENCY.labels(model_name=model_loader.model_name).observe(latency)

        return PredictionResponse(
            customer_id=request.customer_id,
            prediction=prediction,
            probability=round(probability, 4),
            model_version=model_loader.model_version,
            features_used=features_dict,
        )

    except HTTPException:
        raise
    except Exception as e:
        PREDICTION_ERRORS.labels(
            model_name=model_loader.model_name, error_type=type(e).__name__
        ).inc()
        logger.error(f"Prediction error for customer {request.customer_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type="text/plain")
