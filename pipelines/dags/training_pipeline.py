"""
Training Pipeline DAG (Continuous Training) — Airflow 3.x
Implements the full ML pipeline: Fetch → Validate → Train → Evaluate → Promote

This DAG achieves MLOps Level 1 (CT) by automating the entire training loop.
Can be triggered manually, on schedule, or via webhook (drift alert).
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client import models as k8s

# -- Configuration --
ML_IMAGE = "ghcr.io/tiendat1011/mlops/ml-pipeline:latest"
NAMESPACE = "mlops"
MODEL_NAME = "customer_churn_model"

default_args = {
    "owner": "mlops",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

# Common env vars injected into all pipeline steps — secrets from K8s
COMMON_ENV = [
    k8s.V1EnvVar(
        name="AWS_ACCESS_KEY_ID",
        value_from=k8s.V1EnvVarSource(
            secret_key_ref=k8s.V1SecretKeySelector(name="minio-secret", key="MINIO_ROOT_USER")
        ),
    ),
    k8s.V1EnvVar(
        name="AWS_SECRET_ACCESS_KEY",
        value_from=k8s.V1EnvVarSource(
            secret_key_ref=k8s.V1SecretKeySelector(name="minio-secret", key="MINIO_ROOT_PASSWORD")
        ),
    ),
    k8s.V1EnvVar(name="MLFLOW_TRACKING_URI", value="http://mlflow.mlops.svc.cluster.local:5000"),
    k8s.V1EnvVar(name="MLFLOW_S3_ENDPOINT_URL", value="http://minio.mlops.svc.cluster.local:9000"),
    k8s.V1EnvVar(name="AWS_ENDPOINT_URL", value="http://minio.mlops.svc.cluster.local:9000"),
    k8s.V1EnvVar(name="FSSPEC_S3_ENDPOINT_URL", value="http://minio.mlops.svc.cluster.local:9000"),
    k8s.V1EnvVar(name="FEAST_FEATURE_STORE_YAML", value="/opt/feast"),
    k8s.V1EnvVar(name="MODEL_NAME", value=MODEL_NAME),
]


with DAG(
    dag_id="training_pipeline",
    default_args=default_args,
    description="Automated ML training pipeline (CT): Fetch → Validate → Train → Evaluate → Promote",
    schedule="0 4 * * 0",  # Weekly, Sunday 4:00 AM
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
