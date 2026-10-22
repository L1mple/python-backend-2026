import json
from http import HTTPStatus
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs

Send = Callable[[dict[str, Any]], Awaitable[None]]
Receive = Callable[[], Awaitable[dict[str, Any]]]


def fibonacci(n: int) -> int:
    if n <= 1:
        return n

    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b

    return b


def factorial(n: int) -> int:
    result = 1
    for i in range(2, n + 1):
        result *= i

    return result


async def send_response(
    send: Send,
    status: HTTPStatus,
    body: bytes,
    content_type: bytes = b"text/plain",
) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", content_type)],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def send_json(send: Send, status: HTTPStatus, data: Any) -> None:
    await send_response(
        send, status, json.dumps(data).encode(), b"application/json"
    )


async def read_body(receive: Receive) -> bytes:
    body = b""
    while True:
        message = await receive()
        body += message.get("body", b"")
        if not message.get("more_body", False):
            return body


def parse_int(raw: str) -> int | None:
    try:
        return int(raw)
    except ValueError:
        return None


async def factorial_handler(scope: dict[str, Any], receive: Receive, send: Send):
    if scope["method"] != "GET":
        await send_response(send, HTTPStatus.NOT_FOUND, b"Not Found")
        return

    params = parse_qs(scope.get("query_string", b"").decode())
    number = parse_int(params.get("n", [""])[0])

    if number is None:
        await send_response(send, HTTPStatus.UNPROCESSABLE_ENTITY, b"Unprocessable Entity")
        return

    if number < 0:
        await send_response(send, HTTPStatus.BAD_REQUEST, b"Bad Request")
        return

    await send_json(send, HTTPStatus.OK, {"result": factorial(number)})


async def fibonacci_handler(scope: dict[str, Any], receive: Receive, send: Send):
    if scope["method"] != "GET":
        await send_response(send, HTTPStatus.NOT_FOUND, b"Not Found")
        return

    parts = scope.get("path", "").strip("/").split("/")
    if len(parts) != 2:
        await send_response(send, HTTPStatus.UNPROCESSABLE_ENTITY, b"Unprocessable Entity")
        return

    number = parse_int(parts[1])
    if number is None:
        await send_response(send, HTTPStatus.UNPROCESSABLE_ENTITY, b"Unprocessable Entity")
        return

    if number < 0:
        await send_response(send, HTTPStatus.BAD_REQUEST, b"Bad Request")
        return

    await send_json(send, HTTPStatus.OK, {"result": fibonacci(number)})


async def mean_handler(scope: dict[str, Any], receive: Receive, send: Send):
    if scope["method"] != "GET":
        await send_response(send, HTTPStatus.NOT_FOUND, b"Not Found")
        return

    raw = await read_body(receive)
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        await send_response(send, HTTPStatus.UNPROCESSABLE_ENTITY, b"Unprocessable Entity")
        return

    if not isinstance(data, list) or not all(
        isinstance(x, (int, float)) for x in data
    ):
        await send_response(send, HTTPStatus.UNPROCESSABLE_ENTITY, b"Unprocessable Entity")
        return

    if not data:
        await send_response(send, HTTPStatus.BAD_REQUEST, b"Bad Request")
        return

    await send_json(send, HTTPStatus.OK, {"result": sum(data) / len(data)})


URLS = {
    "fibonacci": fibonacci_handler,
    "factorial": factorial_handler,
    "mean": mean_handler,
}


async def application(scope: dict[str, Any], receive: Receive, send: Send):
    scope_type = scope.get("type")

    if scope_type == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return

    if scope_type == "http":
        segments = scope.get("path", "").split("/")
        handler = URLS.get(segments[1]) if len(segments) > 1 else None
        if handler:
            await handler(scope, receive, send)
        else:
            await send_response(send, HTTPStatus.NOT_FOUND, b"Not Found")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
