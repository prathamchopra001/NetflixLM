# Official MLflow image + the Postgres driver and S3 client it lacks (docs/tech-stack.md).
# Version matches mlflow-skinny in uv.lock: the client in nip and the server must agree. The image
# is pinned by digest and the two packages by their uv.lock versions, so rebuilds are identical.
# psycopg 3, not psycopg2: the image's SQLAlchemy 2.1 maps a bare postgresql:// URL to psycopg 3
# (the same URL nip uses), so psycopg2-binary alone fails with "No module named 'psycopg'".
FROM ghcr.io/mlflow/mlflow:v3.17.1@sha256:65aa7a75fe37554bd7dd9e539b58e1ec130dac99f27fef9756df316a272dfee2
RUN pip install --no-cache-dir "psycopg[binary]==3.3.6" "boto3==1.43.114"
