"""
Synthetic Customer Churn Data Generator
Generates realistic customer data for ML pipeline testing.

Usage:
    python generate_data.py                    # Save to local file
    python generate_data.py --upload-minio     # Also upload to MinIO
"""

import argparse
import logging
import os

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_OUTPUT = "/tmp/customer_churn_data.parquet"
N_CUSTOMERS = 10_000


def generate_customer_data(n: int = N_CUSTOMERS, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic customer churn dataset."""
    rng = np.random.default_rng(seed)

    # Customer IDs
    customer_ids = np.arange(1, n + 1)

    # Customer features
    total_purchases = rng.poisson(lam=25, size=n)
    avg_order_value = rng.lognormal(mean=3.5, sigma=0.8, size=n).round(2)
    days_since_last_purchase = rng.exponential(scale=60, size=n).astype(int)
    total_revenue = (total_purchases * avg_order_value).round(2)
    purchase_frequency = rng.gamma(shape=2, scale=1.5, size=n).round(2)

    # Transaction features (7d and 30d windows)
    txn_count_7d = rng.poisson(lam=3, size=n)
    txn_amount_7d = (txn_count_7d * rng.lognormal(mean=3, sigma=0.5, size=n)).round(2)
    txn_count_30d = rng.poisson(lam=12, size=n)
    txn_amount_30d = (txn_count_30d * rng.lognormal(mean=3, sigma=0.5, size=n)).round(2)
    avg_txn_amount_30d = np.where(txn_count_30d > 0, txn_amount_30d / txn_count_30d, 0).round(2)

    # Target: churned (binary)
    # Churn probability increases with days_since_last_purchase and decreases with purchase_frequency
    churn_logit = (
        -2.0
        + 0.015 * days_since_last_purchase
        - 0.3 * purchase_frequency
        - 0.005 * total_purchases
        + rng.normal(0, 0.5, size=n)
    )
    churn_prob = 1 / (1 + np.exp(-churn_logit))
    churned = rng.binomial(1, churn_prob)

    # Timestamps
    event_timestamps = pd.date_range(end=pd.Timestamp.now(), periods=n, freq="min")

    df = pd.DataFrame({
        "customer_id": customer_ids,
        "event_timestamp": event_timestamps,
        "total_purchases": total_purchases,
        "avg_order_value": avg_order_value,
        "days_since_last_purchase": days_since_last_purchase,
        "total_revenue": total_revenue,
        "purchase_frequency": purchase_frequency,
        "txn_count_7d": txn_count_7d,
        "txn_amount_7d": txn_amount_7d,
        "txn_count_30d": txn_count_30d,
        "txn_amount_30d": txn_amount_30d,
        "avg_txn_amount_30d": avg_txn_amount_30d,
        "churned": churned,
    })

    logger.info(f"Generated {len(df)} rows, churn rate: {churned.mean():.1%}")
    return df


def upload_to_minio(filepath: str, bucket: str = "feast-data", object_name: str = "customer_churn_data.parquet"):
    """Upload Parquet file to MinIO."""
    import boto3

    endpoint = os.getenv("MINIO_ENDPOINT", "http://192.168.2.51:31679")
    access_key = os.getenv("AWS_ACCESS_KEY_ID", "mlops-admin")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "changeme-minio-secret-2024")

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )

    s3.upload_file(filepath, bucket, object_name)
    logger.info(f"✅ Uploaded to s3://{bucket}/{object_name}")


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic customer churn data")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output Parquet file path")
    parser.add_argument("--n", type=int, default=N_CUSTOMERS, help="Number of customers")
    parser.add_argument("--upload-minio", action="store_true", help="Upload to MinIO")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    df = generate_customer_data(n=args.n, seed=args.seed)
    df.to_parquet(args.output, index=False)
    logger.info(f"Saved to {args.output}")

    if args.upload_minio:
        upload_to_minio(args.output)

    # Print summary
    print(f"\n{'='*50}")
    print(f"Dataset Summary:")
    print(f"  Rows:        {len(df):,}")
    print(f"  Features:    {len(df.columns) - 3}")  # exclude id, timestamp, target
    print(f"  Churn rate:  {df['churned'].mean():.1%}")
    print(f"  File:        {args.output}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
