import os

import neo4j
import qdrant_client
from minio import Minio


def get_neo4j_driver() -> neo4j.Driver:
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    return neo4j.GraphDatabase.driver(uri, auth=(user, password))


def get_qdrant_client() -> qdrant_client.QdrantClient:
    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    return qdrant_client.QdrantClient(host=host, port=port)


def get_minio_client() -> Minio:
    endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    access_key = os.getenv("MINIO_USER", "minioadmin")
    secret_key = os.getenv("MINIO_PASSWORD", "minioadmin")
    return Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=False)
