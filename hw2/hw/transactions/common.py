import os
import threading
from collections.abc import Callable

from sqlalchemy import Engine, create_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://shop:shop@localhost:5432/shop",
)


def make_engine() -> Engine:
    return create_engine(DATABASE_URL, pool_pre_ping=True)


def run_concurrently(*targets: Callable[[], None]) -> None:
    errors: list[BaseException] = []

    def guarded(target: Callable[[], None]) -> None:
        try:
            target()
        except BaseException as error:
            errors.append(error)

    threads = [threading.Thread(target=guarded, args=(target,)) for target in targets]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    hanging = [thread.name for thread in threads if thread.is_alive()]
    if hanging:
        raise TimeoutError(f"Transactions did not finish: {hanging}")
    if errors:
        raise errors[0]


def heading(title: str) -> None:
    print(f"\n=== {title} ===")
