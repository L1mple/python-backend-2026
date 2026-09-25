import json
import math
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import Any
from urllib.parse import parse_qs

Message = dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
Response = tuple[HTTPStatus, dict[str, Any]]


async def send_json(send: Send, status: HTTPStatus, payload: dict[str, Any]) -> None:
    """Send a JSON response using ASGI messages."""
    body = json.dumps(payload).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def read_body(receive: Receive) -> bytes:
    """Read the complete HTTP request body."""
    chunks = bytearray()
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            break
        chunks.extend(message.get("body", b""))
        if not message.get("more_body", False):
            break
    return bytes(chunks)


async def handle_lifespan(receive: Receive, send: Send) -> None:
    """Acknowledge ASGI startup and shutdown events."""
    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif message["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return


def error(status: HTTPStatus, message: str) -> Response:
    """Build an error response."""
    return status, {"error": message}


def factorial_response(scope: dict[str, Any]) -> Response:
    """Validate the factorial query and calculate its result."""
    try:
        values = parse_qs(
            scope.get("query_string", b"").decode(),
            keep_blank_values=True,
        ).get("n", [])
        if len(values) != 1:
            raise ValueError
        number = int(values[0])
    except (UnicodeDecodeError, ValueError):
        return error(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "Query parameter 'n' must be an integer",
        )

    if number < 0:
        return error(
            HTTPStatus.BAD_REQUEST,
            "Factorial is undefined for negative numbers",
        )
    return HTTPStatus.OK, {"result": math.factorial(number)}


def fibonacci_response(path: str) -> Response:
    """Validate the Fibonacci path parameter and calculate its result."""
    try:
        number = int(path.removeprefix("/fibonacci/"))
    except ValueError:
        return error(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "Path parameter must be an integer",
        )

    if number < 0:
        return error(
            HTTPStatus.BAD_REQUEST,
            "Fibonacci is undefined for negative numbers",
        )

    previous, current = 0, 1
    for _ in range(number):
        previous, current = current, previous + current
    return HTTPStatus.OK, {"result": previous}


async def mean_response(scope: dict[str, Any], receive: Receive) -> Response:
    """Validate a JSON list or query parameter and calculate its mean."""
    try:
        body = await read_body(receive)
        if body:
            numbers = json.loads(body)
        else:
            values = parse_qs(
                scope.get("query_string", b"").decode(),
                keep_blank_values=True,
            ).get("numbers", [])
            if len(values) != 1:
                raise ValueError
            numbers = [float(value) for value in values[0].split(",")]
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return error(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "A list of numbers is required",
        )

    if not isinstance(numbers, list):
        return error(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "A list of numbers is required",
        )
    if not numbers:
        return error(
            HTTPStatus.BAD_REQUEST,
            "The list of numbers must not be empty",
        )
    if not all(
        isinstance(number, (int, float)) and not isinstance(number, bool) and math.isfinite(number)
        for number in numbers
    ):
        return error(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "Every list item must be a finite number",
        )
    return HTTPStatus.OK, {"result": sum(numbers) / len(numbers)}


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

    response = error(HTTPStatus.NOT_FOUND, "Not found")
    if scope.get("method") == "GET":
        path = scope.get("path", "")
        if path == "/factorial":
            response = factorial_response(scope)
        elif path.startswith("/fibonacci/"):
            response = fibonacci_response(path)
        elif path == "/mean":
            response = await mean_response(scope, receive)

    status, payload = response
    await send_json(send, status, payload)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
