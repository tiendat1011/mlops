"""
Unit Tests for Training Module
Tests model convergence and metric calculation.
"""

import os
import sys
import pytest
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def make_training_data(n=500):
    """Create synthetic data for training tests."""
    np.random.seed(42)
    X = pd.DataFrame({
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
    # Target: customers who haven't purchased in > 90 days are "churned"
    y = (X["days_since_last_purchase"] > 90).astype(int)
    return X, y


class TestModelConvergence:
    def test_model_trains_without_error(self):
        """Model should train without throwing errors."""
        X, y = make_training_data()
        model = GradientBoostingClassifier(n_estimators=10, random_state=42)
        model.fit(X, y)
        assert model is not None

    def test_model_overfits_small_sample(self):
        """Model should be able to overfit a small sample (convergence proof)."""
        X, y = make_training_data(50)
        model = GradientBoostingClassifier(n_estimators=100, max_depth=5, random_state=42)
        model.fit(X, y)
        y_pred = model.predict(X)
        train_accuracy = accuracy_score(y, y_pred)
        # Should achieve > 90% on training data (overfitting is expected and desired here)
        assert train_accuracy > 0.90, f"Model should overfit small data, got {train_accuracy:.2%}"

    def test_predictions_are_valid(self):
        """Predictions should be 0 or 1, no NaN."""
        X, y = make_training_data()
        X_train, X_test, y_train, _ = train_test_split(X, y, test_size=0.2, random_state=42)
        model = GradientBoostingClassifier(n_estimators=10, random_state=42)
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        assert not np.any(np.isnan(y_pred)), "Predictions should not contain NaN"
        assert set(y_pred).issubset({0, 1}), "Predictions should be binary (0 or 1)"

    def test_probabilities_sum_to_one(self):
        """Predicted probabilities should sum to ~1."""
        X, y = make_training_data()
        model = GradientBoostingClassifier(n_estimators=10, random_state=42)
        model.fit(X, y)
        proba = model.predict_proba(X)
        sums = proba.sum(axis=1)
        np.testing.assert_allclose(sums, 1.0, atol=1e-6)

    def test_feature_importances_exist(self):
        """All features should have importance values."""
        X, y = make_training_data()
        model = GradientBoostingClassifier(n_estimators=10, random_state=42)
        model.fit(X, y)
        assert len(model.feature_importances_) == X.shape[1]
        assert np.all(model.feature_importances_ >= 0)
