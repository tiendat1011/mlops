FROM tiendat1011/feast-feature-server:latest AS feast-repo

FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies with uv (faster than pip)
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# Copy ML pipeline code
COPY ml/ /app/ml/

# Copy Feast feature repo from the Feast image (config + feature definitions)
COPY --from=feast-repo /app/feature_repo/ /opt/feast/

# Default command (overridden by Airflow KubernetesPodOperator)
CMD ["python", "-m", "ml.train"]
