import json
import math
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import Any
from urllib.parse import parse_qs


async def send_json(
    send: Callable[[dict[str, Any]], Awaitable[None]],
    status: HTTPStatus,
    data: dict[str, Any],
) -> None:
    body = json.dumps(data).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body})


def fibonacci(n: int) -> int:
    previous, current = 0, 1
    for _ in range(n):
        previous, current = current, previous + current
    return previous


async def handle_lifespan(
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


async def handle_factorial(
    scope: dict[str, Any],
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    query = parse_qs(scope["query_string"].decode(), keep_blank_values=True)
    try:
        n = int(query["n"][0])
    except (KeyError, ValueError):
        await send_json(
            send,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {"detail": "Parameter n must be an integer"},
        )
        return

    if n < 0:
        await send_json(send, HTTPStatus.BAD_REQUEST, {"detail": "n must be non-negative"})
        return

    await send_json(send, HTTPStatus.OK, {"result": math.factorial(n)})


async def handle_fibonacci(
    path: str,
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    try:
        n = int(path.removeprefix("/fibonacci/"))
    except ValueError:
        await send_json(
            send,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {"detail": "Path parameter must be an integer"},
        )
        return

    if n < 0:
        await send_json(send, HTTPStatus.BAD_REQUEST, {"detail": "n must be non-negative"})
        return

    await send_json(send, HTTPStatus.OK, {"result": fibonacci(n)})


async def handle_mean(
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    body = b""
    more_body = True
    while more_body:
        message = await receive()
        body += message.get("body", b"")
        more_body = message.get("more_body", False)

    try:
        numbers = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        await send_json(
            send,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {"detail": "A JSON array is required"},
        )
        return

    if not isinstance(numbers, list):
        await send_json(
            send,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {"detail": "A JSON array is required"},
        )
        return
    if not numbers:
        await send_json(send, HTTPStatus.BAD_REQUEST, {"detail": "The array must not be empty"})
        return
    if any(not isinstance(number, (int, float)) or isinstance(number, bool) for number in numbers):
        await send_json(
            send,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {"detail": "All array values must be numbers"},
        )
        return

    await send_json(send, HTTPStatus.OK, {"result": sum(numbers) / len(numbers)})


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

    path = scope["path"]
    method = scope["method"]

    if method != "GET":
        await send_json(send, HTTPStatus.NOT_FOUND, {"detail": "Not found"})
        return

    if path == "/factorial":
        await handle_factorial(scope, send)
        return

    if path.startswith("/fibonacci/"):
        await handle_fibonacci(path, send)
        return

    if path == "/mean":
        await handle_mean(receive, send)
        return

    await send_json(send, HTTPStatus.NOT_FOUND, {"detail": "Not found"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
