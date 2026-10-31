import json
from http import HTTPStatus
from typing import Any, Awaitable, Callable
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
    # TODO: Ваша реализация здесь
    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return

    body = b""
    while True:
        message = await receive()
        if message["type"] == "http.request":
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break

    method = scope.get("method")
    path = scope.get("path", "")
    query_string = scope.get("query_string", b"").decode("utf-8")
    query_params = parse_qs(query_string)

    if path.startswith("/fibonacci/"):
        if method != "GET":
            return await send_response(send, HTTPStatus.NOT_FOUND)
        param = path.replace("/fibonacci/", "")
        status, data = process_fibonacci(param)
        return await send_response(send, status, data)

    elif path == "/factorial":
        if method != "GET":
            return await send_response(send, HTTPStatus.NOT_FOUND)
        status, data = process_factorial(query_params)
        return await send_response(send, status, data)

    elif path == "/mean":
        if method != "GET":
            return await send_response(send, HTTPStatus.NOT_FOUND)
        status, data = process_mean(body, query_params)
        return await send_response(send, status, data)

    else:
        return await send_response(send, HTTPStatus.NOT_FOUND)


async def send_response(
        send: Callable[[dict[str, Any]], Awaitable[None]],
        status_code: int,
        data: dict = None
):
    response_body = b""
    headers = []
    if data is not None:
        response_body = json.dumps(data).encode("utf-8")
        headers.append((b"content-type", b"application/json"))
    headers.append((b"content-length", str(len(response_body)).encode("utf-8")))

    await send({
        "type": "http.response.start",
        "status": status_code,
        "headers": headers,
    })
    await send({
        "type": "http.response.body",
        "body": response_body,
    })

def process_fibonacci(param_str: str) -> tuple[int, dict]:
    try:
        n = int(param_str)
    except ValueError:
        return HTTPStatus.UNPROCESSABLE_ENTITY, {}

    if n < 0:
        return HTTPStatus.BAD_REQUEST, {}

    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return HTTPStatus.OK, {"result": a}


def process_factorial(query_params: dict) -> tuple[int, dict]:
    if "n" not in query_params or len(query_params) != 1:
        return HTTPStatus.UNPROCESSABLE_ENTITY, {}

    n_str = query_params["n"][0]
    try:
        n = int(n_str)
    except ValueError:
        return HTTPStatus.UNPROCESSABLE_ENTITY, {}

    if n < 0:
        return HTTPStatus.BAD_REQUEST, {}

    result = 1
    for i in range(1, n + 1):
        result *= i
    return HTTPStatus.OK, {"result": result}


def process_mean(body: bytes, query_params: dict) -> tuple[int, dict]:
    data = None

    if body:
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return HTTPStatus.UNPROCESSABLE_ENTITY, {}

    elif "numbers" in query_params:
        numbers_str = query_params["numbers"][0]
        if numbers_str == "":
            data = []
        else:
            try:
                data = [float(x) for x in numbers_str.split(",")]
            except ValueError:
                return HTTPStatus.UNPROCESSABLE_ENTITY, {}

    if data is None:
        return HTTPStatus.UNPROCESSABLE_ENTITY, {}

    if not isinstance(data, list):
        return HTTPStatus.UNPROCESSABLE_ENTITY, {}

    if len(data) == 0:
        return HTTPStatus.BAD_REQUEST, {}

    for item in data:
        if not isinstance(item, (int, float)) or isinstance(item, bool):
            return HTTPStatus.BAD_REQUEST, {}

    avg = sum(data) / len(data)
    return HTTPStatus.OK, {"result": avg}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
