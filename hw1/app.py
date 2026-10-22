import json
import math
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs

Send = Callable[[dict[str, Any]], Awaitable[None]]
Receive = Callable[[], Awaitable[dict[str, Any]]]


async def send_json(send: Send, status: int, data: dict[str, Any]) -> None:
    body = json.dumps(data).encode()
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
    body = b""
    while True:
        message = await receive()
        body += message.get("body", b"")
        if not message.get("more_body"):
            return body


async def handle_lifespan(receive: Receive, send: Send) -> None:
    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif message["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return


def fibonacci(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


async def handle_factorial(scope: dict[str, Any], send: Send) -> None:
    params = parse_qs(scope["query_string"].decode())
    values = params.get("n")
    if not values:
        await send_json(send, 422, {"error": "Parameter 'n' is required"})
        return
    try:
        n = int(values[0])
    except ValueError:
        await send_json(send, 422, {"error": "Parameter 'n' must be an integer"})
        return
    if n < 0:
        await send_json(send, 400, {"error": "Parameter 'n' must be non-negative"})
        return
    await send_json(send, 200, {"result": math.factorial(n)})


async def handle_fibonacci(path: str, send: Send) -> None:
    raw = path.removeprefix("/fibonacci/")
    try:
        n = int(raw)
    except ValueError:
        await send_json(send, 422, {"error": "Path parameter must be an integer"})
        return
    if n < 0:
        await send_json(send, 400, {"error": "Path parameter must be non-negative"})
        return
    await send_json(send, 200, {"result": fibonacci(n)})


async def handle_mean(receive: Receive, send: Send) -> None:
    body = await read_body(receive)
    try:
        numbers = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        await send_json(send, 422, {"error": "Body must be a JSON array of numbers"})
        return
    if not isinstance(numbers, list) or not all(
        isinstance(x, (int, float)) and not isinstance(x, bool) for x in numbers
    ):
        await send_json(send, 422, {"error": "Body must be a JSON array of numbers"})
        return
    if not numbers:
        await send_json(send, 400, {"error": "Array must not be empty"})
        return
    await send_json(send, 200, {"result": sum(numbers) / len(numbers)})


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
        await handle_lifespan(receive, send)
        return
    if scope["type"] != "http":
        return

    method = scope["method"]
    path = scope["path"]

    if method == "GET" and path == "/factorial":
        await handle_factorial(scope, send)
    elif method == "GET" and path.startswith("/fibonacci/"):
        await handle_fibonacci(path, send)
    elif method == "GET" and path == "/mean":
        await handle_mean(receive, send)
    else:
        await send_json(send, 404, {"error": "Not found"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
