import json
import math
import urllib
import urllib.parse
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import Any


def asgi_error(error_code, error_msg):
    return {
        "start": {
            "type": "http.response.start",
            "status": error_code,
            "headers": [
                (b"content-type", b"text/plain; charset=utf-8"),
            ],
        },
        "body": {
            "type": "http.response.body",
            "body": error_msg.encode("utf-8"),
        },
    }


def asgi_success(content):
    return {
        "start": {
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"content-type", b"application/json"),
            ],
        },
        "body": {
            "type": "http.response.body",
            "body": json.dumps(content).encode("utf-8"),
        },
    }


def factorial(scope, receive):
    try:
        queries_raw = urllib.parse.parse_qs(scope["query_string"].decode("utf-8"))
        queries_num = int(queries_raw["n"][0])
    except Exception as e:
        return asgi_error(HTTPStatus.UNPROCESSABLE_ENTITY, repr(e))

    if queries_num < 0:
        return asgi_error(
            HTTPStatus.BAD_REQUEST, "Invalid value for n, must be non negative"
        )
    result = math.factorial(queries_num)
    return asgi_success({"result": result})


def fibonaci(scope, receive):
    try:
        n = int(scope["path"].split("/")[-1])
    except Exception as e:
        return asgi_error(HTTPStatus.UNPROCESSABLE_ENTITY, repr(e))

    if n < 0:
        return asgi_error(
            HTTPStatus.BAD_REQUEST, "Invalid value for n, must be non negative"
        )
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return asgi_success({"result": b})


async def mean(scope, receive):
    try:
        body = b""
        more_body = True

        while more_body:
            message = await receive()
            if message["type"] == "http.request":
                body += message.get("body", b"")
                more_body = message.get("more_body", False)
        data = json.loads(body)
        assert isinstance(data, list)
    except Exception as e:
        return asgi_error(HTTPStatus.UNPROCESSABLE_ENTITY, repr(e))

    if len(data) == 0:
        return asgi_error(HTTPStatus.BAD_REQUEST, "Must be non empty array of floats")

    result = sum(data) / len(data)
    return asgi_success({"result": result})


async def router(scope, receive):
    path_parts = scope["path"].split("/")
    if path_parts[1] == "fibonacci":
        return fibonaci(scope, receive)
    elif path_parts[1] == "factorial":
        return factorial(scope, receive)
    elif path_parts[1] == "mean":
        return await mean(scope, receive)
    else:
        return asgi_error(HTTPStatus.NOT_FOUND, "Not found")


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

    result = await router(scope, receive)
    await send(result["start"])
    await send(result["body"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
