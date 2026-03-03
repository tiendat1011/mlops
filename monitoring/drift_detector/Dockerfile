FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
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
