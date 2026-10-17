"""Детерминированная синхронизация шагов между двумя потоками (A и B).

Нужна, чтобы гарантированно воспроизвести конкретный порядок чередования
двух параллельных транзакций (а не полагаться на случайный тайминг
потоков), иначе демонстрация dirty read / non-repeatable read / phantom
read может не воспроизвестись.
"""
import threading


class StepSync:
    def __init__(self) -> None:
        self._events: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def _event(self, name: str) -> threading.Event:
        with self._lock:
            if name not in self._events:
                self._events[name] = threading.Event()
            return self._events[name]

    def signal(self, name: str) -> None:
        self._event(name).set()

    def wait(self, name: str, timeout: float = 10.0) -> None:
        if not self._event(name).wait(timeout):
            raise TimeoutError(f"Timed out waiting for step '{name}'")
