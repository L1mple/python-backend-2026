from os import getenv

from sqlalchemy import URL


def make_database_url() -> str | URL:
    password = getenv("DATABASE_PASSWORD")
    if password is None:
        raise RuntimeError("DATABASE_PASSWORD is required")

    return URL.create(
        "mssql+pymssql",
        username=getenv("DATABASE_USER", "sa"),
        password=password,
        host=getenv("DATABASE_HOST", "database"),
        port=int(getenv("DATABASE_PORT", "1433")),
        database=getenv("DATABASE_NAME", "master"),
    )
