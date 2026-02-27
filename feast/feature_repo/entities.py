"""
Feast Entity Definitions
Entities represent the primary keys used to look up features.
"""

from feast import Entity, ValueType

# Customer entity — used for customer-level features
customer = Entity(
    name="customer_id",
    value_type=ValueType.INT64,
    description="Unique identifier for a customer",
    join_keys=["customer_id"],
)

# Product entity — used for product-level features (optional)
product = Entity(
    name="product_id",
    value_type=ValueType.INT64,
    description="Unique identifier for a product",
    join_keys=["product_id"],
)
