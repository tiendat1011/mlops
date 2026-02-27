"""
Basic tests for the Serving API.
"""

import pytest
from app.schemas import PredictionRequest, PredictionResponse, HealthResponse


class TestSchemas:
    def test_prediction_request_valid(self):
        req = PredictionRequest(customer_id=12345)
        assert req.customer_id == 12345

    def test_prediction_request_invalid(self):
        with pytest.raises(Exception):
            PredictionRequest(customer_id="not_a_number")

    def test_prediction_response(self):
        resp = PredictionResponse(
            customer_id=1,
            prediction=1,
            probability=0.85,
            model_version="3",
            features_used={"total_purchases": 10},
        )
        assert resp.prediction == 1
        assert resp.probability == 0.85

    def test_health_response(self):
        resp = HealthResponse(
            status="healthy",
            model_loaded=True,
            model_name="test_model",
            model_version="1",
        )
        assert resp.model_loaded is True
