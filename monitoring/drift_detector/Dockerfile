FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN uv pip install --system --no-cache \
    evidently>=0.4.0 \
    prometheus-client>=0.21.0 \
    pandas>=2.2.0 \
    numpy>=1.26.0 \
    scipy>=1.14.0 \
    mlflow>=3.9.0 \
    boto3>=1.35.0 \
    httpx>=0.28.0

COPY main.py /app/

EXPOSE 9090

CMD ["python", "main.py"]
