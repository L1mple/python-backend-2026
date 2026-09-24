import json
import math
from http import HTTPStatus
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs


async def send_json(send, status: int, data: dict[str, Any]) -> None:
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


async def send_error(send, status: HTTPStatus) -> None:
    await send_json(send, status, {"detail": status.phrase})


async def read_body(receive) -> bytes:
    body = b""
    more_body = True
    while more_body:
        message = await receive()
        body += message.get("body", b"")
        more_body = message.get("more_body", False)
    return body


async def handle_lifespan(receive, send) -> None:
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


async def handle_factorial(scope, send) -> None:
    query = parse_qs(scope["query_string"].decode(), keep_blank_values=True)
    values = query.get("n")
    if not values:
        return await send_error(send, HTTPStatus.UNPROCESSABLE_ENTITY)

    try:
        n = int(values[0])
    except ValueError:
        return await send_error(send, HTTPStatus.UNPROCESSABLE_ENTITY)

    if n < 0:
        return await send_error(send, HTTPStatus.BAD_REQUEST)

    await send_json(send, HTTPStatus.OK, {"result": math.factorial(n)})


async def handle_fibonacci(param: str, send) -> None:
    try:
        n = int(param)
    except ValueError:
        return await send_error(send, HTTPStatus.UNPROCESSABLE_ENTITY)

    if n < 0:
        return await send_error(send, HTTPStatus.BAD_REQUEST)

    await send_json(send, HTTPStatus.OK, {"result": fibonacci(n)})


async def handle_mean(receive, send) -> None:
    body = await read_body(receive)
    try:
        numbers = json.loads(body)
    except ValueError:
        return await send_error(send, HTTPStatus.UNPROCESSABLE_ENTITY)

    if not isinstance(numbers, list):
        return await send_error(send, HTTPStatus.UNPROCESSABLE_ENTITY)

    # bool is a subclass of int, so it has to be excluded explicitly
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in numbers):
        return await send_error(send, HTTPStatus.UNPROCESSABLE_ENTITY)

    if not numbers:
        return await send_error(send, HTTPStatus.BAD_REQUEST)

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
        return await handle_lifespan(receive, send)

    if scope["type"] != "http":
        return

    method = scope["method"]
    path = scope["path"]

    if method == "GET" and path == "/factorial":
        return await handle_factorial(scope, send)

    if method == "GET" and path.startswith("/fibonacci/"):
        return await handle_fibonacci(path.removeprefix("/fibonacci/"), send)

    if method == "GET" and path == "/mean":
        return await handle_mean(receive, send)

    await send_error(send, HTTPStatus.NOT_FOUND)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
