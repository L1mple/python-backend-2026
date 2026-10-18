from os import getenv

from sqlalchemy import URL


def make_database_url() -> str | URL:
    host = getenv("DATABASE_HOST")
    if host is None:
        return getenv("DATABASE_URL", "sqlite:///./db.sqlite3")

    password = getenv("DATABASE_PASSWORD")
    if password is None:
        raise RuntimeError("DATABASE_PASSWORD is required")

    return URL.create(
        "mssql+pymssql",
        username=getenv("DATABASE_USER", "sa"),
        password=password,
        host=host,
        port=int(getenv("DATABASE_PORT", "1433")),
        database=getenv("DATABASE_NAME", "master"),
    )
