"""
Feast Data Source Definitions
Define where raw feature data lives.
"""

from feast import FileSource
from feast.data_format import ParquetFormat

# Customer features stored as Parquet files
# In production, these Parquet files would be on MinIO (s3://feast-data/customer_features/)
# For local dev, use a local path
customer_source = FileSource(
    name="customer_features_source",
    path="s3://feast-data/customer_features.parquet",  # MinIO S3-compatible path
    file_format=ParquetFormat(),
    timestamp_field="event_timestamp",
    created_timestamp_column="created_timestamp",
    description="Customer behavioral features computed from transaction data",
)

# Transaction features source
transaction_source = FileSource(
    name="transaction_features_source",
    path="s3://feast-data/transaction_features.parquet",
    file_format=ParquetFormat(),
    timestamp_field="event_timestamp",
    created_timestamp_column="created_timestamp",
    description="Aggregated transaction features",
)
