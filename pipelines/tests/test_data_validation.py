"""
Unit Tests for Data Validation
"""

import pandas as pd
import numpy as np
import pytest

# Adjust import path for test
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ml.data_validation import validate_schema, validate_nulls, validate_statistics, EXPECTED_COLUMNS


def make_valid_df(n=200):
    """Create a valid sample dataframe."""
    np.random.seed(42)
    return pd.DataFrame({
        "customer_id": range(n),
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


class TestValidateSchema:
    def test_valid_schema(self):
        df = make_valid_df()
        errors = validate_schema(df)
        assert errors == []

    def test_missing_column(self):
        df = make_valid_df().drop(columns=["total_purchases"])
        errors = validate_schema(df)
        assert len(errors) == 1
        assert "total_purchases" in errors[0]

    def test_extra_columns_ok(self):
        df = make_valid_df()
        df["extra_col"] = 0
        errors = validate_schema(df)
        assert errors == []  # Extra columns are warnings, not errors


class TestValidateNulls:
    def test_no_nulls(self):
        df = make_valid_df()
        errors = validate_nulls(df)
        assert errors == []

    def test_excessive_nulls(self):
        df = make_valid_df(200)
        # Set 20% of total_purchases to null (exceeds 5% threshold)
        df.loc[:39, "total_purchases"] = np.nan
        errors = validate_nulls(df)
        assert len(errors) == 1
        assert "total_purchases" in errors[0]


class TestValidateStatistics:
    def test_valid_statistics(self):
        df = make_valid_df()
        errors = validate_statistics(df)
        assert errors == []

    def test_negative_counts(self):
        df = make_valid_df()
        df.loc[0, "total_purchases"] = -5
        errors = validate_statistics(df)
        assert len(errors) == 1
        assert "negative" in errors[0].lower()
