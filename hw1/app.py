import json
import math
import re
from http import HTTPStatus
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs

_INT_RE = re.compile(r"[+-]?[0-9]+")


def _parse_int(raw: str) -> int | None:
    """Строго разбирает целое число; на мусор возвращает None."""
    if _INT_RE.fullmatch(raw) is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _factorial(n: int) -> int:
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result


def _fibonacci(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


async def _send_json(
    send: Callable[[dict[str, Any]], Awaitable[None]],
    status: int,
    payload: dict[str, Any],
) -> None:
    body = json.dumps(payload).encode()
    await send(
        {
            "type": "http.response.start",
            "status": int(status),
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def _read_body(receive: Callable[[], Awaitable[dict[str, Any]]]) -> bytes:
    chunks: list[bytes] = []
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            break
        chunks.append(message.get("body", b""))
        if not message.get("more_body", False):
            break
    return b"".join(chunks)


async def _handle_lifespan(
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    # TestClient ждет lifespan.startup.complete при входе в `async with`.
    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif message["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return


async def _handle_factorial(query_string: bytes, send) -> None:
    params = parse_qs(query_string.decode("latin-1"), keep_blank_values=True)
    values = params.get("n")
    n = _parse_int(values[0]) if values else None
    if n is None:
        await _send_json(send, HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "n must be an integer"})
    elif n < 0:
        await _send_json(send, HTTPStatus.BAD_REQUEST, {"error": "n must be non-negative"})
    else:
        await _send_json(send, HTTPStatus.OK, {"result": _factorial(n)})


async def _handle_fibonacci(raw_n: str, send) -> None:
    n = _parse_int(raw_n)
    if n is None:
        await _send_json(send, HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "n must be an integer"})
    elif n < 0:
        await _send_json(send, HTTPStatus.BAD_REQUEST, {"error": "n must be non-negative"})
    else:
        await _send_json(send, HTTPStatus.OK, {"result": _fibonacci(n)})


def _is_number(value: Any) -> bool:
    # bool - подкласс int, но `true` в списке чисел числом не считаем
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, float) and math.isfinite(value)


async def _handle_mean(receive, send) -> None:
    body = await _read_body(receive)
    if not body.strip():
        await _send_json(send, HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "JSON body is required"})
        return

    try:
        numbers = json.loads(body)
    except (ValueError, RecursionError):
        await _send_json(send, HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "invalid JSON"})
        return

    if not isinstance(numbers, list) or not all(_is_number(x) for x in numbers):
        await _send_json(send, HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "body must be a JSON array of numbers"})
        return

    if not numbers:
        await _send_json(send, HTTPStatus.BAD_REQUEST, {"error": "array must not be empty"})
        return

    await _send_json(send, HTTPStatus.OK, {"result": sum(numbers) / len(numbers)})


async def application(
    scope: dict[str, Any],
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
):
    """
    Args:
        scope: Словарь с информацией о запросе
        receive: Корутина для получения сообщений от клиента
        send: Корутина для отправки сообщений клиенту
    """
    if scope["type"] == "lifespan":
        await _handle_lifespan(receive, send)
        return

    if scope["type"] != "http":
        return

    method: str = scope["method"]
    path: str = scope["path"]

    if method == "GET":
        if path == "/factorial":
            await _handle_factorial(scope.get("query_string", b""), send)
            return
        if path == "/mean":
            await _handle_mean(receive, send)
            return
        if path.startswith("/fibonacci/") and "/" not in path[len("/fibonacci/"):]:
            raw_n = path[len("/fibonacci/"):]
            if raw_n:
                await _handle_fibonacci(raw_n, send)
                return

    await _send_json(send, HTTPStatus.NOT_FOUND, {"error": "not found"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
