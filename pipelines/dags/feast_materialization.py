"""
Feast Materialization DAG — Airflow 3.x
Runs daily to sync features from Offline Store → Online Store (Redis).
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client import models as k8s

FEAST_IMAGE = "tiendat1011/feast-feature-server:latest"

default_args = {
    "owner": "mlops",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

# MinIO/S3 env vars — inject from K8s Secrets
S3_ENV_VARS = [
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
    k8s.V1EnvVar(name="AWS_ENDPOINT_URL", value="http://minio.mlops.svc.cluster.local:9000"),
    k8s.V1EnvVar(name="FSSPEC_S3_ENDPOINT_URL", value="http://minio.mlops.svc.cluster.local:9000"),
    k8s.V1EnvVar(name="FEAST_FEATURE_STORE_YAML", value="/app/feature_repo/feature_store.yaml"),
]

with DAG(
    dag_id="feast_materialization",
    default_args=default_args,
    description="Daily materialization: sync offline features to Redis online store",
    schedule="0 2 * * *",  # Every day at 2:00 AM
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["feast", "feature-store", "materialization"],
) as dag:

    materialize = KubernetesPodOperator(
        task_id="feast_materialize",
        name="feast-materialize",
        namespace="mlops",
        image=FEAST_IMAGE,
        cmds=["feast"],
        arguments=[
            "materialize-incremental",
            "{{ ds }}T00:00:00",
        ],
        env_vars=S3_ENV_VARS,
        startup_timeout_seconds=300,
        get_logs=True,
        is_delete_operator_pod=True,
        in_cluster=True,
    )
