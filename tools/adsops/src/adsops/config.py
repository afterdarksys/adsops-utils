import os


def get_db_url() -> str:
    """Build PostgreSQL connection URL from env vars matching Go hostctl."""
    host = os.environ.get("INVENTORY_DB_HOST", "afterdarksys.com")
    port = os.environ.get("INVENTORY_DB_PORT", "5432")
    dbname = os.environ.get("INVENTORY_DB_NAME", "inventory")
    user = os.environ.get("INVENTORY_DB_USER")
    password = os.environ.get("INVENTORY_DB_PASSWORD")
    if not user:
        raise RuntimeError("INVENTORY_DB_USER environment variable is required")
    if not password:
        raise RuntimeError("INVENTORY_DB_PASSWORD environment variable is required")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}?sslmode=require"
