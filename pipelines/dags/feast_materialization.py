"""
Feast Materialization DAG — Airflow 3.x
Runs daily to sync features from Offline Store → Online Store (Redis).
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator

default_args = {
    "owner": "mlops",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

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
        image="{{ var.value.feast_image | default('tiendat1011/feast-feature-server') }}",
        cmds=["feast"],
        arguments=[
            "materialize-incremental",
            "{{ ds }}T00:00:00",
        ],
        env_vars={
            "FEAST_FEATURE_STORE_YAML": "/app/feature_repo/feature_store.yaml",
        },
        startup_timeout_seconds=300,
        get_logs=True,
        is_delete_operator_pod=True,
        in_cluster=True,
    )
