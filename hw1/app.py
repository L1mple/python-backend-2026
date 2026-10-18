from http import HTTPStatus
from typing import Any, Awaitable, Callable
import json
import math
from urllib.parse import parse_qs


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
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return

    path = scope["path"]
    method = scope["method"]

    query_string = scope.get("query_string").decode()
    query_params = parse_qs(query_string)

    body = b""
    while True:
        message = await receive()
        if message["type"] == "http.request":
            body += message.get("body")
            if not message.get("more_body", False):
                break

    path_parts = [p for p in path.split("/") if p]

    try:
        if path == "/factorial" and method == "GET":
            await handle_factorial(query_params, send)
        elif len(path_parts) == 2 and path_parts[0] == "fibonacci" and method == "GET":
            await handle_fibonacci(path_parts[1], send)
        elif path == "/mean" and method == "GET":
            await handle_mean(body, send)
        else:
            await send_response(send, HTTPStatus.NOT_FOUND, {"error": "Not found"})
    except Exception as e:
        await send_response(send, HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(e)})


async def send_response(
    send: Callable[[dict[str, Any]], Awaitable[None]],
    status_code: int,
    data: dict[str, Any],
):
    """Отправляет JSON ответ"""
    response_body = json.dumps(data).encode()

    await send({
        "type": "http.response.start",
        "status": status_code,
        "headers": [
            [b"content-type", b"application/json"],
            [b"content-length", str(len(response_body)).encode()],
        ],
    })

    await send({
        "type": "http.response.body",
        "body": response_body,
    })


async def handle_factorial(
    query_params: dict[str, list[str]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
):
    if "n" not in query_params:
        await send_response(
            send,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {"error": "Parameter 'n' is required"},
        )
        return

    value = query_params["n"][0]

    try:
        n = int(value)
    except (ValueError, TypeError):
        await send_response(
            send,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {"error": "Parameter 'n' must be an integer"},
        )
        return

    if n < 0:
        await send_response(
            send,
            HTTPStatus.BAD_REQUEST,
            {"error": "Parameter 'n' must be non-negative"},
        )
        return

    if n > 1000:
        await send_response(
            send,
            HTTPStatus.BAD_REQUEST,
            {"error": "Parameter 'n' is too large"},
        )
        return

    result = math.factorial(n)
    await send_response(send, HTTPStatus.OK, {"result": result})


async def handle_fibonacci(
    n_str: str,
    send: Callable[[dict[str, Any]], Awaitable[None]],
):
    try:
        n = int(n_str)
    except (ValueError, TypeError):
        await send_response(
            send,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {"error": "Invalid integer"},
        )
        return

    if n < 0:
        await send_response(
            send,
            HTTPStatus.BAD_REQUEST,
            {"error": "Parameter 'n' must be non-negative"},
        )
        return

    if n > 10000:
        await send_response(
            send,
            HTTPStatus.BAD_REQUEST,
            {"error": "Parameter 'n' is too large"},
        )
        return

    if n <= 1:
        result = n
    else:
        a, b = 0, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        result = b

    await send_response(send, HTTPStatus.OK, {"result": result})


async def handle_mean(
    body: bytes,
    send: Callable[[dict[str, Any]], Awaitable[None]],
):
    if not body:
        await send_response(
            send,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {"error": "Body is required"},
        )
        return

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        await send_response(
            send,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {"error": "Invalid JSON"},
        )
        return

    if data is None:
        await send_response(
            send,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {"error": "Body is required"},
        )
        return

    if not isinstance(data, list) or len(data) == 0:
        await send_response(
            send,
            HTTPStatus.BAD_REQUEST,
            {"error": "Body must be a non-empty list"},
        )
        return

    for item in data:
        if not isinstance(item, (int, float)) or isinstance(item, bool):
            await send_response(
                send,
                HTTPStatus.BAD_REQUEST,
                {"error": "All items must be numbers"},
            )
            return

    result = sum(data) / len(data)
    await send_response(send, HTTPStatus.OK, {"result": result})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
