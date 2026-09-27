from typing import Iterator


def int_id_generator() -> Iterator[int]:
    i = 0
    while True:
        yield i
        i += 1
