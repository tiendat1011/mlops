FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir feast[redis,postgres,aws]==0.40.0

COPY feature_repo/ /app/feature_repo/

WORKDIR /app/feature_repo

# Apply feature definitions to the registry
RUN feast apply

# Default command: run the Feast feature server
CMD ["feast", "serve", "--host", "0.0.0.0", "--port", "6566"]
