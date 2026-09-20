import json
from http import HTTPStatus
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs


async def send_json(send, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [(b"content-type", b"application/json")],
    })
    await send({
        "type": "http.response.body",
        "body": body,
    })


def factorial(n: int) -> int:
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result


def fibonacci(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


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

    method = scope["method"]
    path = scope["path"]

    if method != "GET":
        await send_json(send, HTTPStatus.NOT_FOUND, {"error": "not found"})
        return

    if path == "/factorial":
        query = parse_qs(scope["query_string"].decode())
        n_values = query.get("n")
        if not n_values:
            await send_json(send, HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "n is required"})
            return
        try:
            n = int(n_values[0])
        except ValueError:
            await send_json(send, HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "n must be an integer"})
            return
        if n < 0:
            await send_json(send, HTTPStatus.BAD_REQUEST, {"error": "n must be non-negative"})
            return
        await send_json(send, HTTPStatus.OK, {"result": factorial(n)})
        return

    if path.startswith("/fibonacci/"):
        n_str = path.removeprefix("/fibonacci/")
        try:
            n = int(n_str)
        except ValueError:
            await send_json(send, HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "n must be an integer"})
            return
        if n < 0:
            await send_json(send, HTTPStatus.BAD_REQUEST, {"error": "n must be non-negative"})
            return
        await send_json(send, HTTPStatus.OK, {"result": fibonacci(n)})
        return

    if path == "/mean":
        message = await receive()
        body = message.get("body", b"")
        try:
            numbers = json.loads(body)
        except ValueError:
            await send_json(send, HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "valid JSON body is required"})
            return
        if not isinstance(numbers, list) or not all(isinstance(x, (int, float)) for x in numbers):
            await send_json(send, HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "body must be a list of numbers"})
            return
        if not numbers:
            await send_json(send, HTTPStatus.BAD_REQUEST, {"error": "list must not be empty"})
            return
        await send_json(send, HTTPStatus.OK, {"result": sum(numbers) / len(numbers)})
        return

    await send_json(send, HTTPStatus.NOT_FOUND, {"error": "not found"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
