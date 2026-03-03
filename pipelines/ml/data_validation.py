"""
Data Validation Module
Checks data quality before model training: schema, nulls, and statistical properties.

Usage: python -m ml.data_validation
"""

import os
import sys
import logging

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATA_INPUT_PATH = os.getenv("DATA_OUTPUT_PATH", "/tmp/training_data.parquet")

# Expected schema definition
EXPECTED_COLUMNS = {
    "customer_id": "int64",
    "total_purchases": "int64",
    "avg_order_value": "float64",
    "days_since_last_purchase": "int64",
    "total_revenue": "float64",
    "purchase_frequency": "float64",
    "txn_count_7d": "int64",
    "txn_amount_7d": "float64",
    "txn_count_30d": "int64",
    "txn_amount_30d": "float64",
    "avg_txn_amount_30d": "float64",
}

# Maximum allowed null ratio per column
MAX_NULL_RATIO = 0.05  # 5%

# Minimum number of rows required
MIN_ROWS = 100


def validate_schema(df: pd.DataFrame) -> list[str]:
    """Check that all expected columns are present."""
    errors = []
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            errors.append(f"Missing expected column: {col}")
    unexpected = set(df.columns) - set(EXPECTED_COLUMNS.keys()) - {"event_timestamp", "created_timestamp"}
    if unexpected:
        logger.warning(f"Unexpected columns found (may be OK): {unexpected}")
    return errors


def validate_nulls(df: pd.DataFrame) -> list[str]:
    """Check null ratios are within acceptable limits."""
    errors = []
    for col in EXPECTED_COLUMNS:
        if col in df.columns:
            null_ratio = df[col].isna().mean()
            if null_ratio > MAX_NULL_RATIO:
                errors.append(
                    f"Column '{col}' has {null_ratio:.1%} nulls (max: {MAX_NULL_RATIO:.1%})"
                )
    return errors


def validate_statistics(df: pd.DataFrame) -> list[str]:
    """Check basic statistical properties (no negative counts, no NaN values after cleaning)."""
    errors = []

    # Count columns should be non-negative
    count_cols = ["total_purchases", "txn_count_7d", "txn_count_30d"]
    for col in count_cols:
        if col in df.columns and (df[col].dropna() < 0).any():
            errors.append(f"Column '{col}' contains negative values")

    # Revenue/amount columns should not have extreme outliers (> 10 std devs)
    amount_cols = ["avg_order_value", "total_revenue", "txn_amount_7d", "txn_amount_30d"]
    for col in amount_cols:
        if col in df.columns:
            clean = df[col].dropna()
            if len(clean) > 0:
                mean, std = clean.mean(), clean.std()
                if std > 0:
                    outlier_ratio = ((clean - mean).abs() > 10 * std).mean()
                    if outlier_ratio > 0.01:  # More than 1% extreme outliers
                        errors.append(
                            f"Column '{col}' has {outlier_ratio:.2%} extreme outliers (>10σ)"
                        )

    return errors


def validate_data() -> bool:
    """Run all data validation checks. Returns True if data passes."""
    # Download from S3 (each pipeline step runs in a separate Pod)
    from ml.s3_storage import download_artifact
    try:
        download_artifact("pipeline/training_data.parquet", DATA_INPUT_PATH)
    except Exception as e:
        logger.warning(f"S3 download failed, trying local file: {e}")

    logger.info(f"Loading data from {DATA_INPUT_PATH}...")
    df = pd.read_parquet(DATA_INPUT_PATH)
    logger.info(f"Loaded {df.shape[0]} rows, {df.shape[1]} columns")

    all_errors = []

    # Check minimum rows
    if len(df) < MIN_ROWS:
        all_errors.append(f"Insufficient data: {len(df)} rows (min: {MIN_ROWS})")

    # Run validations
    all_errors.extend(validate_schema(df))
    all_errors.extend(validate_nulls(df))
    all_errors.extend(validate_statistics(df))

    if all_errors:
        logger.error("❌ Data validation FAILED:")
        for err in all_errors:
            logger.error(f"  - {err}")
        return False

    logger.info("✅ Data validation PASSED — all checks OK")
    logger.info(f"  Rows: {len(df)}")
    logger.info(f"  Columns: {len(df.columns)}")
    logger.info(f"  Null summary:\n{df.isnull().sum().to_string()}")
    return True


if __name__ == "__main__":
    success = validate_data()
    if not success:
        sys.exit(1)
