import json
from http import HTTPStatus
from typing import Any, Awaitable, Callable


Scope = dict[str, Any]
Message = dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]


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

    if scope["type"] != "http":
        return

    method = scope["method"]
    path = scope["path"]
    query_string = scope.get("query_string", b"").decode()

    query_params = {}
    if query_string:
        for pair in query_string.split("&"):
            if "=" in pair:
                key, value = pair.split("=", 1)
                query_params[key] = value
            else:
                query_params[pair] = ""

    if path == "/factorial" and method == "GET":
        await handle_factorial(query_params, send)
    elif path.startswith("/fibonacci/") and method == "GET":
        await handle_fibonacci(path, send)
    elif path == "/mean" and method == "GET":
        await handle_mean(scope, receive, send)
    else:
        await send_response(send, HTTPStatus.NOT_FOUND, {"error": "Not found"})

    
async def send_response(send: Send, status: int, body: dict) -> None:
    body_bytes = json.dumps(body).encode()
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body_bytes)).encode()),
        ],
    })
    await send({
        "type": "http.response.body",
        "body": body_bytes,
    })


async def handle_factorial(query_params: dict, send: Send) -> None:
    if "n" not in query_params:
        await send_response(send, HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "Missing parameter n"})
        return

    n_str = query_params["n"]
    if n_str == "":
        await send_response(send, HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "Empty parameter"})
        return

    try:
        n = int(n_str)
    except ValueError:
        await send_response(send, HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "Invalid parameter"})
        return

    if n < 0:
        await send_response(send, HTTPStatus.BAD_REQUEST, {"error": "Negative not allowed"})
        return

    result = 1
    for i in range(2, n + 1):
        result *= i

    await send_response(send, HTTPStatus.OK, {"result": result})


async def handle_fibonacci(path: str, send: Send) -> None:
    n_str = path[len("/fibonacci/"):]
    
    try:
        n = int(n_str)
    except ValueError:
        await send_response(send, HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "Invalid parameter"})
        return

    if n < 0:
        await send_response(send, HTTPStatus.BAD_REQUEST, {"error": "Negative not allowed"})
        return

    if n == 0:
        result = 0
    elif n == 1:
        result = 1
    else:
        a, b = 0, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        result = b

    await send_response(send, HTTPStatus.OK, {"result": result})


async def handle_mean(scope: Scope, receive: Receive, send: Send) -> None:
    query_string = scope.get("query_string", b"").decode()
    query_params = {}
    if query_string:
        for pair in query_string.split("&"):
            if "=" in pair:
                key, value = pair.split("=", 1)
                query_params[key] = value
            else:
                query_params[pair] = ""

    if "numbers" in query_params:
        numbers_str = query_params["numbers"]
        if numbers_str == "":
            await send_response(send, HTTPStatus.BAD_REQUEST, {"error": "Empty list"})
            return
        try:
            data = [float(x) for x in numbers_str.split(",")]
        except ValueError:
            await send_response(send, HTTPStatus.BAD_REQUEST, {"error": "Invalid numbers"})
            return
    else:
        body = b""
        while True:
            message = await receive()
            if message["type"] == "http.request":
                body += message.get("body", b"")
                if not message.get("more_body", False):
                    break

        if not body:
            await send_response(send, HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "No body"})
            return

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            await send_response(send, HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "Invalid JSON"})
            return

    if data is None:
        await send_response(send, HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "Null not allowed"})
        return

    if not isinstance(data, list):
        await send_response(send, HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "Expected list"})
        return

    if len(data) == 0:
        await send_response(send, HTTPStatus.BAD_REQUEST, {"error": "Empty list"})
        return

    for item in data:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            await send_response(send, HTTPStatus.BAD_REQUEST, {"error": "Non-numeric element"})
            return

    result = sum(data) / len(data)
    await send_response(send, HTTPStatus.OK, {"result": result})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
