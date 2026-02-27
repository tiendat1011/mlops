"""
Feast Feature View Definitions
FeatureViews map entities to features from data sources.
"""

from datetime import timedelta

from feast import FeatureView, Field
from feast.types import Float64, Int64

from data_sources import customer_source, transaction_source
from entities import customer

# ── Customer Behavioral Features ────────────────────────
customer_features = FeatureView(
    name="customer_features",
    entities=[customer],
    ttl=timedelta(days=7),  # Features expire after 7 days if not refreshed
    schema=[
        Field(name="total_purchases", dtype=Int64, description="Total number of purchases"),
        Field(name="avg_order_value", dtype=Float64, description="Average order value (currency)"),
        Field(name="days_since_last_purchase", dtype=Int64, description="Days since the last purchase"),
        Field(name="total_revenue", dtype=Float64, description="Total revenue from this customer"),
        Field(name="purchase_frequency", dtype=Float64, description="Purchases per month"),
    ],
    source=customer_source,
    online=True,   # Materialize to Redis for online serving
    tags={"team": "data-science", "version": "v1"},
)

# ── Transaction Aggregation Features ────────────────────
transaction_features = FeatureView(
    name="transaction_features",
    entities=[customer],
    ttl=timedelta(days=3),
    schema=[
        Field(name="txn_count_7d", dtype=Int64, description="Transaction count in last 7 days"),
        Field(name="txn_amount_7d", dtype=Float64, description="Total transaction amount last 7 days"),
        Field(name="txn_count_30d", dtype=Int64, description="Transaction count in last 30 days"),
        Field(name="txn_amount_30d", dtype=Float64, description="Total transaction amount last 30 days"),
        Field(name="avg_txn_amount_30d", dtype=Float64, description="Average txn amount last 30 days"),
    ],
    source=transaction_source,
    online=True,
    tags={"team": "data-science", "version": "v1"},
)
