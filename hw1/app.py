import json
import math
from http import HTTPStatus
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs


Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]


async def send_json(send: Send, status: HTTPStatus, payload: dict[str, Any]) -> None:
    """Send a complete JSON response using ASGI messages."""
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": int(status),
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def read_request_body(receive: Receive) -> bytes:
    """Read the whole request body, including bodies split into several chunks."""
    chunks: list[bytes] = []

    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            break
        if message["type"] != "http.request":
            continue

        chunks.append(message.get("body", b""))
        if not message.get("more_body", False):
            break

    return b"".join(chunks)


def parse_integer_parameter(scope: dict[str, Any], name: str) -> int | None:
    """Return a single integer query parameter or None for invalid input."""
    try:
        query = parse_qs(
            scope.get("query_string", b"").decode("utf-8"),
            keep_blank_values=True,
        )
    except UnicodeDecodeError:
        return None

    values = query.get(name)
    if values is None or len(values) != 1:
        return None

    value = values[0]
    if not value or (value[0] == "-" and not value[1:].isdigit()) or (
        value[0] != "-" and not value.isdigit()
    ):
        return None

    return int(value)


def fibonacci(n: int) -> int:
    """Calculate the n-th Fibonacci number iteratively."""
    previous, current = 0, 1
    for _ in range(n):
        previous, current = current, previous + current
    return previous


async def handle_factorial(scope: dict[str, Any], send: Send) -> None:
    n = parse_integer_parameter(scope, "n")
    if n is None:
        await send_json(
            send,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {"detail": "Query parameter 'n' must be an integer"},
        )
        return
    if n < 0:
        await send_json(
            send,
            HTTPStatus.BAD_REQUEST,
            {"detail": "Factorial is not defined for negative numbers"},
        )
        return

    await send_json(send, HTTPStatus.OK, {"result": math.factorial(n)})


async def handle_fibonacci(path: str, send: Send) -> None:
    raw_n = path.removeprefix("/fibonacci/")
    if not raw_n or (raw_n[0] == "-" and not raw_n[1:].isdigit()) or (
        raw_n[0] != "-" and not raw_n.isdigit()
    ):
        await send_json(
            send,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {"detail": "Path parameter 'n' must be an integer"},
        )
        return

    n = int(raw_n)
    if n < 0:
        await send_json(
            send,
            HTTPStatus.BAD_REQUEST,
            {"detail": "Fibonacci is not defined for negative numbers"},
        )
        return

    await send_json(send, HTTPStatus.OK, {"result": fibonacci(n)})


async def handle_mean(receive: Receive, send: Send) -> None:
    body = await read_request_body(receive)
    try:
        numbers = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        await send_json(
            send,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {"detail": "Request body must contain a JSON array of numbers"},
        )
        return

    if not isinstance(numbers, list) or any(
        isinstance(number, bool)
        or not isinstance(number, (int, float))
        or (isinstance(number, float) and not math.isfinite(number))
        for number in numbers
    ):
        await send_json(
            send,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {"detail": "Request body must contain a JSON array of numbers"},
        )
        return
    if not numbers:
        await send_json(
            send,
            HTTPStatus.BAD_REQUEST,
            {"detail": "Cannot calculate the mean of an empty array"},
        )
        return

    await send_json(
        send,
        HTTPStatus.OK,
        {"result": sum(numbers) / len(numbers)},
    )


async def handle_lifespan(receive: Receive, send: Send) -> None:
    """Acknowledge application startup and shutdown events."""
    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif message["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return


async def application(
    scope: dict[str, Any],
    receive: Receive,
    send: Send,
) -> None:
    """
    Args:
        scope: Словарь с информацией о запросе
        receive: Корутина для получения сообщений от клиента
        send: Корутина для отправки сообщений клиенту
    """
    if scope.get("type") == "lifespan":
        await handle_lifespan(receive, send)
        return
    if scope.get("type") != "http":
        return

    method = scope.get("method", "").upper()
    path = scope.get("path", "")

    if method != "GET":
        await send_json(send, HTTPStatus.NOT_FOUND, {"detail": "Not found"})
    elif path == "/factorial":
        await handle_factorial(scope, send)
    elif path.startswith("/fibonacci/"):
        await handle_fibonacci(path, send)
    elif path == "/mean":
        await handle_mean(receive, send)
    else:
        await send_json(send, HTTPStatus.NOT_FOUND, {"detail": "Not found"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
