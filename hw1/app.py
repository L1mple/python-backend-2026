import json
import math
import re
from http import HTTPStatus
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs

_INT_RE = re.compile(r"[+-]?\d+")


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

    body = await _read_body(receive)
    method = scope["method"]
    path = scope["path"]

    if method != "GET":
        await _send_json(send, HTTPStatus.NOT_FOUND, {"detail": "Not аound"})
        return

    if path == "/factorial":
        await _handle_factorial(scope, send)
        return

    if path == "/mean":
        await _handle_mean(body, send)
        return

    argument = _fibonacci_argument(path)
    if argument is None:
        await _send_json(send, HTTPStatus.NOT_FOUND, {"detail": "Not found"})
        return

    await _handle_fibonacci(argument, send)


def _fibonacci_argument(path: str) -> str | None:
    prefix = "/fibonacci/"
    if not path.startswith(prefix):
        return None
    argument = path[len(prefix):]

    if not argument or "/" in argument:
        return None
    return argument


def _query_value(scope: dict[str, Any], name: str) -> str | None:
    raw_query = scope.get("query_string", b"")
    if isinstance(raw_query, bytes):
        raw_query = raw_query.decode()

    parsed = parse_qs(raw_query, keep_blank_values=True)
    values = parsed.get(name)

    if not values:
        return None
    return values[0]


def _parse_int(raw: str) -> int | None:
    if _INT_RE.fullmatch(raw) is None:
        return None
    return int(raw)


def _parse_numbers(body: bytes) -> list[float] | None:
    if not body.strip():
        return None
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, list):
        return None

    numbers: list[float] = []
    for item in payload:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return None
        numbers.append(float(item))
    return numbers


def _fibonacci(n: int) -> int:
    previous, current = 0, 1
    for _ in range(n):
        previous, current = current, previous + current
    return previous


async def _handle_factorial(
    scope: dict[str, Any],
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    raw = _query_value(scope, "n")
    number = None if raw is None else _parse_int(raw)

    if number is None:
        await _send_json(
            send,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {"detail": "Invalid value for n"},
        )
        return

    if number < 0:
        await _send_json(
            send,
            HTTPStatus.BAD_REQUEST,
            {"detail": "Invalid value for n, must be non-negative"},
        )
        return

    await _send_json(send, HTTPStatus.OK, {"result": math.factorial(number)})


async def _handle_fibonacci(
    raw: str,
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    number = _parse_int(raw)

    if number is None:
        await _send_json(
            send,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {"detail": "Invalid vaule for n"},
        )
        return

    if number < 0:
        await _send_json(
            send,
            HTTPStatus.BAD_REQUEST,
            {"detail": "Invalid value for n, must be non-negative"},
        )
        return

    await _send_json(send, HTTPStatus.OK, {"result": _fibonacci(number)})


async def _handle_mean(
    body: bytes,
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    numbers = _parse_numbers(body)

    if numbers is None:
        await _send_json(
            send,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {"detail": "Invalid value for body, must be an array of numbers"},
        )
        return

    if not numbers:
        await _send_json(
            send,
            HTTPStatus.BAD_REQUEST,
            {"detail": "Invalid value for body, must be a non-empty array of numbers"},
        )
        return

    await _send_json(send, HTTPStatus.OK, {"result": sum(numbers) / len(numbers)})


async def _read_body(
    receive: Callable[[], Awaitable[dict[str, Any]]],
) -> bytes:
    chunks: list[bytes] = []

    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            break
        chunks.append(message.get("body", b""))
        if not message.get("more_body", False):
            break
    return b"".join(chunks)


async def _send_json(
    send: Callable[[dict[str, Any]], Awaitable[None]],
    status: HTTPStatus,
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
    await send({"type": "http.response.body", "body": body, "more_body": False})


async def _handle_lifespan(
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif message["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
