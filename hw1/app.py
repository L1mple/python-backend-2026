import json
import math
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs
import re

ROUTE_PATTERN = re.compile(r'^/(?P<name>[^/]+)(?:/(?P<arg>[^/]+))?/?$')

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
    # TODO: Ваша реализация здесь
    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                break
        return

    if scope["type"] == "http" and scope["method"] == "GET":
        path = scope["path"]
        matched_pattern = ROUTE_PATTERN.match(path)

        if matched_pattern is None:
            await send_not_found(send)
            return

        extracted_data = matched_pattern.groupdict()

        if extracted_data["name"] == "factorial":
            query_string = scope["query_string"].decode("utf-8")
            params = parse_qs(query_string)

            if not params or list(params.keys()) != ["n"] or len(params["n"]) != 1:
                await send_unprocessable(send)
                return

            n_str = params["n"][0]

            if not n_str:
                await send_unprocessable(send)
                return

            if n_str.startswith("-") and n_str[1:].isdigit():
                await send_bad_request(send)
                return

            if not n_str.isdigit():
                await send_unprocessable(send)
                return

            n_val = int(n_str)
            factorial_result = math.factorial(n_val)

            await send_ok(factorial_result, send)
            return
        elif extracted_data["name"] == "fibonacci" and extracted_data["arg"] is not None:
            n_str = extracted_data["arg"]

            if n_str.startswith("-") and n_str[1:].isdigit():
                await send_bad_request(send)
                return

            if not n_str.isdigit():
                await send_unprocessable(send)
                return

            n_val = int(n_str)
            fibonacci_result = fibonacci(n_val)

            await send_ok(fibonacci_result, send)
            return
        elif extracted_data["name"] == "mean":
            body = b""
            more_body = True

            while more_body:
                message = await receive()
                body += message.get("body", b"")
                more_body = message.get("more_body", False)

            try:
                data = json.loads(body.decode("utf-8"))

            except (json.decoder.JSONDecodeError, UnicodeDecodeError):
                await send_not_found(send)
                return

            if data is None:
                await send_unprocessable(send)
                return

            if len(data) == 0:
                await send_bad_request(send)
                return

            mean_result = sum(data) / len(data)

            await send_ok(mean_result, send)
            return
        else:
            await send_not_found(send)
            return
    await send_not_found(send)


async def send_ok(n: Any, send: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
    response_data = {"result": n}
    response_bytes = json.dumps(response_data).encode("utf-8")

    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(response_bytes)).encode("utf-8")),
        ]
    })

    await send({
        "type": "http.response.body",
        "body": response_bytes,
    })


async def send_not_found(send: Callable[[dict[str, Any]], Awaitable[None]]):
    await send({
        "type": "http.response.start",
        "status": 404,
        "headers": [
            (b"content-type", b"text/plain; charset=utf-8")
        ]
    })

    await send({
        "type": "http.response.body",
        "body": b"Not Found"
    })

async def send_unprocessable(send: Callable[[dict[str, Any]], Awaitable[None]]):
    await send({
        "type": "http.response.start",
        "status": 422,
        "headers": [
            (b"content-type", b"text/plain; charset=utf-8")
        ]
    })

    await send({
        "type": "http.response.body",
        "body": b"Unprocessable"
    })

async def send_bad_request(send: Callable[[dict[str, Any]], Awaitable[None]]):
    await send({
        "type": "http.response.start",
        "status": 400,
        "headers": [
            (b"content-type", b"text/plain; charset=utf-8")
        ]
    })

    await send({
        "type": "http.response.body",
        "body": b"Bad Request"
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
