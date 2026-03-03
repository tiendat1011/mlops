FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install Feast with all backends + s3fs for MinIO access
RUN uv pip install --system --no-cache \
    "feast[redis,postgres,aws]>=0.40.1" \
    s3fs \
    psycopg2-binary

# Copy feature definitions (entities, features, data sources)
COPY feature_repo/ /app/feature_repo/

WORKDIR /app/feature_repo

# Note: feast apply runs as init container in K8s, not baked in image
# For local dev/testing:
#   docker run --rm feast-feature-server feast apply
#   docker run -p 6566:6566 feast-feature-server

EXPOSE 6566

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:6566/health')" || exit 1

CMD ["feast", "serve", "--host", "0.0.0.0", "--port", "6566"]
