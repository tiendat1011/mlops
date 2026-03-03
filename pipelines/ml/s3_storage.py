"""
S3 Storage Helper — Read/write intermediate pipeline data via MinIO.

Each pipeline step runs in a separate K8s Pod, so /tmp is NOT shared.
This module provides transparent S3 ↔ local file bridging.
"""

import os
import logging

import boto3

logger = logging.getLogger(__name__)

PIPELINE_BUCKET = os.getenv("PIPELINE_BUCKET", "mlops-pipeline")
S3_ENDPOINT = os.getenv("AWS_ENDPOINT_URL", "http://minio.mlops.svc.cluster.local:9000")


def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )


def _ensure_bucket(s3):
    """Create the pipeline bucket if it doesn't exist."""
    try:
        s3.head_bucket(Bucket=PIPELINE_BUCKET)
    except Exception:
        try:
            s3.create_bucket(Bucket=PIPELINE_BUCKET)
            logger.info(f"Created bucket: {PIPELINE_BUCKET}")
        except Exception as e:
            logger.warning(f"Bucket creation failed (may already exist): {e}")


def upload_artifact(local_path: str, s3_key: str) -> str:
    """Upload a local file to S3. Returns the S3 URI."""
    s3 = _get_s3_client()
    _ensure_bucket(s3)
    s3.upload_file(local_path, PIPELINE_BUCKET, s3_key)
    uri = f"s3://{PIPELINE_BUCKET}/{s3_key}"
    logger.info(f"Uploaded {local_path} → {uri}")
    return uri


def download_artifact(s3_key: str, local_path: str) -> str:
    """Download a file from S3 to local. Returns the local path."""
    s3 = _get_s3_client()
    s3.download_file(PIPELINE_BUCKET, s3_key, local_path)
    logger.info(f"Downloaded s3://{PIPELINE_BUCKET}/{s3_key} → {local_path}")
    return local_path
