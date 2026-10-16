# Official MLflow image + the Postgres driver and S3 client it lacks (docs/tech-stack.md).
# Version matches mlflow-skinny in uv.lock: the client in nip and the server must agree.
# psycopg 3, not psycopg2: the image's SQLAlchemy 2.1 maps a bare postgresql:// URL to psycopg 3
# (the same URL nip uses), so psycopg2-binary alone fails with "No module named 'psycopg'".
FROM ghcr.io/mlflow/mlflow:v3.17.1
RUN pip install --no-cache-dir "psycopg[binary]" boto3
