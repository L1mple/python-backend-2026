import json
import math
import re
from http import HTTPStatus
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs

_INT_RE = re.compile(r"[+-]?\d+")
_FIBONACCI_PREFIX = "/fibonacci/"


def _parse_int(raw: str) -> int | None:
    """Строгий разбор целого числа (без пробелов и подчеркиваний)."""
    if not _INT_RE.fullmatch(raw):
        return None
    return int(raw)


def _fibonacci(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


async def _send_json(
    send: Callable[[dict[str, Any]], Awaitable[None]],
    status: int,
    payload: dict[str, Any],
    extra_headers: list[tuple[bytes, bytes]] | None = None,
) -> None:
    body = json.dumps(payload).encode("utf-8")
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode()),
    ]
    headers.extend(extra_headers or [])
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


async def _send_error(
    send: Callable[[dict[str, Any]], Awaitable[None]],
    status: HTTPStatus,
    detail: str,
    extra_headers: list[tuple[bytes, bytes]] | None = None,
) -> None:
    await _send_json(send, status, {"detail": detail}, extra_headers)


async def _read_body(receive: Callable[[], Awaitable[dict[str, Any]]]) -> bytes:
    body = b""
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            break
        body += message.get("body", b"")
        if not message.get("more_body", False):
            break
    return body


async def _handle_lifespan(receive, send) -> None:
    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif message["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return


async def _factorial(scope, send) -> None:
    query = parse_qs(scope.get("query_string", b"").decode("latin-1"), keep_blank_values=True)
    values = query.get("n")
    if not values:
        return await _send_error(send, HTTPStatus.UNPROCESSABLE_ENTITY, "Query parameter 'n' is required")

    n = _parse_int(values[0])
    if n is None:
        return await _send_error(send, HTTPStatus.UNPROCESSABLE_ENTITY, "Query parameter 'n' must be an integer")
    if n < 0:
        return await _send_error(send, HTTPStatus.BAD_REQUEST, "Invalid value for n, must be non-negative")

    await _send_json(send, HTTPStatus.OK, {"result": math.factorial(n)})


async def _fibonacci_handler(raw_n: str, send) -> None:
    n = _parse_int(raw_n)
    if n is None:
        return await _send_error(send, HTTPStatus.UNPROCESSABLE_ENTITY, "Path parameter 'n' must be an integer")
    if n < 0:
        return await _send_error(send, HTTPStatus.BAD_REQUEST, "Invalid value for n, must be non-negative")

    await _send_json(send, HTTPStatus.OK, {"result": _fibonacci(n)})


async def _mean(receive, send) -> None:
    raw = await _read_body(receive)
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return await _send_error(send, HTTPStatus.UNPROCESSABLE_ENTITY, "Body must be a valid JSON array of numbers")

    is_valid = isinstance(data, list) and all(
        isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in data
    )
    if not is_valid:
        return await _send_error(send, HTTPStatus.UNPROCESSABLE_ENTITY, "Body must be a JSON array of numbers")
    if not data:
        return await _send_error(
            send, HTTPStatus.BAD_REQUEST, "Invalid value for body, must be non-empty array of floats"
        )

    await _send_json(send, HTTPStatus.OK, {"result": sum(data) / len(data)})


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
        return await _handle_lifespan(receive, send)
    if scope["type"] != "http":
        return

    method = scope["method"]
    path = scope["path"]

    if path == "/factorial":
        handler = lambda: _factorial(scope, send)  # noqa: E731
    elif path.startswith(_FIBONACCI_PREFIX) and "/" not in path[len(_FIBONACCI_PREFIX):]:
        handler = lambda: _fibonacci_handler(path[len(_FIBONACCI_PREFIX):], send)  # noqa: E731
    elif path == "/mean":
        handler = lambda: _mean(receive, send)  # noqa: E731
    else:
        return await _send_error(send, HTTPStatus.NOT_FOUND, "Not Found")

    if method != "GET":
        return await _send_error(
            send, HTTPStatus.METHOD_NOT_ALLOWED, "Method Not Allowed", [(b"allow", b"GET")]
        )

    await handler()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
