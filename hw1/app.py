import json
import math
from fractions import Fraction
from http import HTTPStatus
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs

_INTEGER_CHUNK_DIGITS = 1000
_INTEGER_CHUNK_BASE = 10**_INTEGER_CHUNK_DIGITS


def _integer_to_decimal(value: int) -> str:
    if value == 0:
        return "0"

    sign = "-" if value < 0 else ""
    value = abs(value)
    chunks: list[int] = []
    while value:
        value, remainder = divmod(value, _INTEGER_CHUNK_BASE)
        chunks.append(remainder)

    head = str(chunks.pop())
    tail = "".join(
        f"{chunk:0{_INTEGER_CHUNK_DIGITS}d}" for chunk in reversed(chunks)
    )
    return sign + head + tail


async def _send_json(
    send: Callable[[dict[str, Any]], Awaitable[None]],
    status: HTTPStatus,
    payload: dict[str, Any],
) -> None:
    result = payload.get("result")
    if len(payload) == 1 and type(result) is int:
        body = f'{{"result": {_integer_to_decimal(result)}}}'.encode("ascii")
    else:
        body = json.dumps(payload, allow_nan=False).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": int(status),
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def _read_body(
    receive: Callable[[], Awaitable[dict[str, Any]]],
) -> bytes:
    chunks: list[bytes] = []
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            raise ConnectionError("Client disconnected before sending the full body")
        if message["type"] != "http.request":
            raise ValueError("Unexpected ASGI message type")
        chunks.append(message.get("body", b""))
        if not message.get("more_body", False):
            return b"".join(chunks)


def _parse_integer(value: str | None) -> int:
    if value is None or value == "":
        raise ValueError("Missing integer")
    return int(value)


def _factorial(n: int) -> int:
    result = 1
    for value in range(2, n + 1):
        result *= value
    return result


def _fibonacci(n: int) -> int:
    current, following = 0, 1
    for _ in range(n):
        current, following = following, current + following
    return current


async def application(
    scope: dict[str, Any],
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    """
    Args:
        scope: Словарь с информацией о запросе
        receive: Корутина для получения сообщений от клиента
        send: Корутина для отправки сообщений клиенту
    """
    if scope.get("type") == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return
            else:
                raise ValueError("Unexpected ASGI lifespan message type")

    if scope.get("type") != "http":
        return

    method = scope.get("method", "")
    path = scope.get("path", "")

    if method == "GET" and path == "/factorial":
        try:
            query = parse_qs(
                scope.get("query_string", b"").decode("utf-8"),
                keep_blank_values=True,
            )
            values = query.get("n", [])
            if len(values) != 1:
                raise ValueError("Expected one n value")
            n = _parse_integer(values[0])
        except (UnicodeDecodeError, ValueError):
            await _send_json(
                send,
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"error": "n must be an integer"},
            )
            return

        if n < 0:
            await _send_json(
                send,
                HTTPStatus.BAD_REQUEST,
                {"error": "n must be non-negative"},
            )
            return

        await _send_json(send, HTTPStatus.OK, {"result": _factorial(n)})
        return

    if method == "GET" and path.startswith("/fibonacci/"):
        try:
            n = _parse_integer(path.removeprefix("/fibonacci/"))
        except ValueError:
            await _send_json(
                send,
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"error": "n must be an integer"},
            )
            return

        if n < 0:
            await _send_json(
                send,
                HTTPStatus.BAD_REQUEST,
                {"error": "n must be non-negative"},
            )
            return

        await _send_json(send, HTTPStatus.OK, {"result": _fibonacci(n)})
        return

    if method == "GET" and path == "/mean":
        try:
            body = await _read_body(receive)
            if not body:
                raise ValueError("Missing JSON body")
            numbers = json.loads(body)
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            RecursionError,
            ValueError,
        ):
            await _send_json(
                send,
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"error": "body must be a JSON array of numbers"},
            )
            return

        if not isinstance(numbers, list) or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or (isinstance(value, float) and not math.isfinite(value))
            for value in numbers
        ):
            await _send_json(
                send,
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"error": "body must be a JSON array of numbers"},
            )
            return

        if not numbers:
            await _send_json(
                send,
                HTTPStatus.BAD_REQUEST,
                {"error": "at least one number is required"},
            )
            return

        try:
            total = sum((Fraction(value) for value in numbers), start=Fraction())
            result = float(total / len(numbers))
        except OverflowError:
            await _send_json(
                send,
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"error": "mean is outside the supported numeric range"},
            )
            return

        if not math.isfinite(result):
            await _send_json(
                send,
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"error": "mean is outside the supported numeric range"},
            )
            return

        await _send_json(send, HTTPStatus.OK, {"result": result})
        return

    await _send_json(send, HTTPStatus.NOT_FOUND, {"error": "Not found"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
