"""
Pydantic schemas for request/response models.
"""

from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    """Request body for prediction endpoint."""
    customer_id: int = Field(..., description="Customer ID to get prediction for", examples=[12345])

    model_config = {"json_schema_extra": {"examples": [{"customer_id": 12345}]}}


class PredictionResponse(BaseModel):
    """Response body for prediction endpoint."""
    customer_id: int
    prediction: int = Field(..., description="Predicted class (0=not churned, 1=churned)")
    probability: float = Field(..., description="Probability of churn (0.0 to 1.0)")
    model_version: str = Field(..., description="Model version used for prediction")
    features_used: dict = Field(default_factory=dict, description="Features retrieved from Feast")


class HealthResponse(BaseModel):
    """Response for health check."""
    status: str
    model_loaded: bool
    model_name: str
    model_version: str
