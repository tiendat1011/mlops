"""
Training Pipeline DAG (Continuous Training)
Implements the full ML pipeline: Fetch → Validate → Train → Evaluate → Promote

This DAG achieves MLOps Level 1 (CT) by automating the entire training loop.
Can be triggered manually, on schedule, or via webhook (drift alert).
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator

# -- Configuration --
ML_IMAGE = "{{ var.value.ml_pipeline_image | default('ml-pipeline:latest') }}"
NAMESPACE = "mlops"
MODEL_NAME = "{{ var.value.model_name | default('customer_churn_model') }}"

default_args = {
    "owner": "mlops",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

# Common env vars injected into all pipeline steps
COMMON_ENV = {
    "MLFLOW_TRACKING_URI": "http://mlflow.mlops.svc.cluster.local:5000",
    "MLFLOW_S3_ENDPOINT_URL": "http://minio.mlops.svc.cluster.local:9000",
    "AWS_ACCESS_KEY_ID": "mlops-admin",
    "AWS_SECRET_ACCESS_KEY": "changeme-minio-secret-2024",
    "FEAST_FEATURE_STORE_YAML": "/opt/feast/feature_store.yaml",
    "MODEL_NAME": MODEL_NAME,
}


with DAG(
    dag_id="training_pipeline",
    default_args=default_args,
    description="Automated ML training pipeline (CT): Fetch → Validate → Train → Evaluate → Promote",
    schedule_interval="0 4 * * 0",  # Weekly, Sunday 4:00 AM
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["ml", "training", "ct", "pipeline"],
    # Allow triggering via API (for drift-based retraining)
    params={
        "retrain_reason": "scheduled",
    },
) as dag:

    # ── Step 1: Fetch Training Data from Feast ──────────────
    fetch_data = KubernetesPodOperator(
        task_id="fetch_data",
        name="ml-fetch-data",
        namespace=NAMESPACE,
        image=ML_IMAGE,
        cmds=["python", "-m", "ml.fetch_data"],
        env_vars=COMMON_ENV,
        startup_timeout_seconds=300,
        get_logs=True,
        is_delete_operator_pod=True,
        in_cluster=True,
    )

    # ── Step 2: Validate Data Quality ───────────────────────
    validate_data = KubernetesPodOperator(
        task_id="validate_data",
        name="ml-validate-data",
        namespace=NAMESPACE,
        image=ML_IMAGE,
        cmds=["python", "-m", "ml.data_validation"],
        env_vars=COMMON_ENV,
        startup_timeout_seconds=300,
        get_logs=True,
        is_delete_operator_pod=True,
        in_cluster=True,
    )

    # ── Step 3: Train Model ─────────────────────────────────
    train_model = KubernetesPodOperator(
        task_id="train_model",
        name="ml-train-model",
        namespace=NAMESPACE,
        image=ML_IMAGE,
        cmds=["python", "-m", "ml.train"],
        env_vars=COMMON_ENV,
        startup_timeout_seconds=600,
        get_logs=True,
        is_delete_operator_pod=True,
        in_cluster=True,
        # Uncomment for GPU nodes:
        # node_selector={"gpu": "true"},
        # container_resources={
        #     "requests": {"cpu": "2", "memory": "4Gi", "nvidia.com/gpu": "1"},
        #     "limits": {"cpu": "4", "memory": "8Gi", "nvidia.com/gpu": "1"},
        # },
    )

    # ── Step 4: Evaluate & Compare with Champion ────────────
    evaluate_model = KubernetesPodOperator(
        task_id="evaluate_model",
        name="ml-evaluate-model",
        namespace=NAMESPACE,
        image=ML_IMAGE,
        cmds=["python", "-m", "ml.evaluate"],
        env_vars=COMMON_ENV,
        startup_timeout_seconds=300,
        get_logs=True,
        is_delete_operator_pod=True,
        in_cluster=True,
    )

    # ── Step 5: Promote Model if Better ─────────────────────
    promote_model = KubernetesPodOperator(
        task_id="promote_model",
        name="ml-promote-model",
        namespace=NAMESPACE,
        image=ML_IMAGE,
        cmds=["python", "-m", "ml.promote"],
        env_vars=COMMON_ENV,
        startup_timeout_seconds=300,
        get_logs=True,
        is_delete_operator_pod=True,
        in_cluster=True,
    )

    # ── Pipeline DAG ────────────────────────────────────────
    fetch_data >> validate_data >> train_model >> evaluate_model >> promote_model
