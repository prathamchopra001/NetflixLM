import os


def database_url() -> str:
    """NIP_DATABASE_URL with the psycopg 3 driver (a bare postgresql:// would pick psycopg2).

    Unset → a host-less URL: enough for offline SQL rendering (`alembic upgrade head --sql`).
    """
    url = os.environ.get("NIP_DATABASE_URL", "postgresql://")
    return url.replace("postgresql://", "postgresql+psycopg://", 1)
