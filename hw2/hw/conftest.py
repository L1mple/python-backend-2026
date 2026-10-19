import os
import subprocess
import time

import pytest


def _run(cmd: list[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, check=False, capture_output=True, text=True)


def _is_postgres_ready(cwd: str) -> bool:
    result = _run(
        ["docker", "compose", "exec", "-T", "postgres", "pg_isready", "-U", "postgres"],
        cwd,
    )
    return result.returncode == 0


@pytest.fixture(scope="session", autouse=True)
def _postgres_up():
    """Поднимает postgres из docker-compose перед тестами и гасит после."""
    cwd = os.path.dirname(os.path.abspath(__file__))

    already = _run(["docker", "compose", "ps", "-q", "postgres"], cwd)
    if already.stdout.strip():
        # контейнер уже есть (локальный запуск) — просто ждём готовности
        for _ in range(30):
            if _is_postgres_ready(cwd):
                break
            time.sleep(1)
        os.environ.setdefault(
            "DATABASE_URL",
            "postgresql+asyncpg://postgres:password@localhost:7432/hw4_db",
        )
        yield
        return

    # контейнера нет (CI) — поднимаем
    _run(["docker", "compose", "up", "-d", "postgres"], cwd)
    for _ in range(60):
        if _is_postgres_ready(cwd):
            break
        time.sleep(1)
    else:
        raise RuntimeError("postgres не поднялся за 60 секунд")

    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:password@localhost:7432/hw4_db",
    )

    yield

    _run(["docker", "compose", "down", "-v"], cwd)