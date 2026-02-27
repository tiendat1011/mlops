# MLOps Platform Architecture

## Overview

Nền tảng MLOps Level 2 trên Kubernetes, thực hiện Continuous Integration, Continuous Delivery, và Continuous Training cho Machine Learning.

## Architecture Diagram

```mermaid
graph TB
    subgraph "Data Sources"
        DWH["Data Warehouse / S3"]
    end

    subgraph "Feature Store (Feast)"
        FS_OFFLINE["Offline Store<br/>(Parquet on MinIO)"]
        FS_ONLINE["Online Store<br/>(Redis)"]
        FS_REG["Registry<br/>(PostgreSQL)"]
    end

    subgraph "Storage Layer"
        MINIO["MinIO<br/>(S3-compatible)"]
        PG["PostgreSQL"]
        REDIS["Redis"]
    end

    subgraph "ML Pipeline (Airflow DAGs)"
        FETCH["Fetch Data"]
        VALIDATE["Validate Data"]
        TRAIN["Train Model"]
        EVAL["Evaluate Model"]
        PROMOTE["Promote Model"]
        FETCH --> VALIDATE --> TRAIN --> EVAL --> PROMOTE
    end

    subgraph "Experiment Tracking"
        MLFLOW["MLflow Server"]
        MLFLOW_REG["Model Registry"]
    end

    subgraph "Model Serving"
        API["FastAPI<br/>(/predict)"]
        APISIX["APISIX Gateway"]
    end

    subgraph "Monitoring"
        DRIFT["Evidently AI<br/>Drift Detector"]
        PROM["Prometheus"]
        GRAF["Grafana"]
    end

    subgraph "CI/CD"
        GIT["Git Repository"]
        GHA["GitHub Actions"]
        ARGOCD["ArgoCD"]
    end

    DWH --> FS_OFFLINE
    FS_OFFLINE -->|materialize| FS_ONLINE
    FETCH -->|get_historical_features| FS_OFFLINE
    TRAIN -->|log params/metrics| MLFLOW
    PROMOTE -->|transition_stage| MLFLOW_REG
    API -->|load model| MLFLOW_REG
    API -->|get_online_features| FS_ONLINE
    APISIX --> API
    API -->|prediction logs| DRIFT
    DRIFT -->|metrics| PROM
    PROM --> GRAF
    GRAF -->|alert webhook| FETCH
    GIT --> GHA
    GHA -->|build image| ARGOCD
    ARGOCD -->|deploy| API
    MLFLOW --> MINIO
    MLFLOW --> PG
    FS_REG --> PG
    FS_ONLINE --> REDIS
```

## Component Summary

| Component | Image/Chart | Purpose | Port |
|---|---|---|---|
| MinIO | `quay.io/minio/minio` | S3-compatible object storage | 9000/9001 |
| PostgreSQL | `postgres:16-alpine` | Metadata backend (MLflow, Airflow, Feast) | 5432 |
| Redis | `redis:7-alpine` | Feast Online Store | 6379 |
| MLflow | `ghcr.io/mlflow/mlflow` | Experiment tracking + Model Registry | 5000 |
| Airflow | `apache/airflow` (Helm) | Pipeline orchestration (KubernetesExecutor) | 8080 |
| Feast | Custom image | Feature Store | 6566 |
| FastAPI Serving | Custom image | Model prediction API | 8000 |
| Drift Detector | Custom image | Data drift monitoring | 9090 |
| APISIX | Existing | API Gateway (rate-limit, auth) | — |
| ArgoCD | Existing | GitOps deployment | — |
| Prometheus | Existing | Metrics collection | — |
| Grafana | Existing | Dashboards & alerting | — |

## Deployment Order

```
1. kubectl apply -k infrastructure/          # MinIO, Postgres, Redis, MLflow
2. helm install airflow apache-airflow/airflow -n mlops -f infrastructure/airflow/helm-values.yaml
3. feast apply (from feast/feature_repo/)    # Register features
4. Trigger training_pipeline DAG             # Train first model
5. kubectl apply -f serving/k8s/             # Deploy serving API
6. kubectl apply -f monitoring/k8s/          # Deploy drift detector
```
