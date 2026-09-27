import json
from http import HTTPStatus
from math import factorial as math_factorial
from typing import Any, Awaitable, Callable


async def send_response(
    send: Callable[[dict[str, Any]], Awaitable[None]],
    status_code: int,
    body: dict[str, Any] | None = None,
) -> None:
    """Отправить HTTP-ответ с JSON-телом (или пустым телом)."""
    payload = json.dumps(body).encode() if body is not None else b""
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(payload)).encode()),
            ],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": payload,
        }
    )


async def read_body(receive: Callable[[], Awaitable[dict[str, Any]]]) -> bytes:
    """Прочитать тело запроса целиком (может приходить частями)."""
    body = b""
    while True:
        message = await receive()
        if message["type"] == "http.request":
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break
        elif message["type"] == "http.disconnect":
            break
    return body


def fibonacci(n: int) -> int:
    """n-е число Фибоначчи (fib(0)=0, fib(1)=1)."""
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
        return

    if scope["type"] != "http":
        return

    method = scope["method"]
    path = scope["path"]
    query_string = scope.get("query_string", b"").decode()

    query: dict[str, str] = {}
    if query_string:
        for pair in query_string.split("&"):
            if "=" in pair:
                key, _, value = pair.partition("=")
                query[key] = value
            else:
                query[pair] = ""

    if method == "GET" and path.startswith("/fibonacci/"):
        raw = path[len("/fibonacci/") :]

        if not raw.lstrip("-").isdigit():
            await send_response(send, HTTPStatus.UNPROCESSABLE_ENTITY)
            return
        n = int(raw)
        if n < 0:
            await send_response(send, HTTPStatus.BAD_REQUEST)
            return
        await send_response(send, HTTPStatus.OK, {"result": fibonacci(n)})
        return

    if method == "GET" and path == "/factorial":
        if "n" not in query or query["n"] == "":
            await send_response(send, HTTPStatus.UNPROCESSABLE_ENTITY)
            return
        raw = query["n"]
        if not raw.lstrip("-").isdigit():
            await send_response(send, HTTPStatus.UNPROCESSABLE_ENTITY)
            return
        n = int(raw)
        if n < 0:
            await send_response(send, HTTPStatus.BAD_REQUEST)
            return
        await send_response(send, HTTPStatus.OK, {"result": math_factorial(n)})
        return

    if method == "GET" and path == "/mean":
        body = await read_body(receive)
        if not body:
            await send_response(send, HTTPStatus.UNPROCESSABLE_ENTITY)
            return
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            await send_response(send, HTTPStatus.UNPROCESSABLE_ENTITY)
            return
        if not isinstance(data, list):
            await send_response(send, HTTPStatus.UNPROCESSABLE_ENTITY)
            return
        if len(data) == 0:
            await send_response(send, HTTPStatus.BAD_REQUEST)
            return
        if not all(
            isinstance(x, (int, float)) and not isinstance(x, bool)
            for x in data
        ):
            await send_response(send, HTTPStatus.BAD_REQUEST)
            return
        await send_response(
            send, HTTPStatus.OK, {"result": sum(data) / len(data)}
        )
        return

    await send_response(send, HTTPStatus.NOT_FOUND)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
