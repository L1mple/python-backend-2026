from typing import Any, Awaitable, Callable
import json
import math
from http import HTTPStatus
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

    if scope["type"] != "http":
        return

    method = scope["method"]
    path = scope["path"]
    query_string = scope.get("query_string", b"").decode("utf-8")
    query_params = parse_qs(query_string)

    body = b""
    while True:
        message = await receive()
        if message["type"] == "http.request":
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break
        elif message["type"] == "http.disconnect":
            return

    async def send_response(status: int, headers, payload):
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": headers + [(b"content-length", str(len(payload)).encode())],
        })
        await send({
            "type": "http.response.body",
            "body": payload,
        })

    async def send_error(status: int):
        await send_response(status, [], b"")

    async def send_json(status: int, data: dict[str, Any]):
        await send_response(status,
                   [(b"content-type", b"application/json")],
                   json.dumps(data).encode("utf-8")
                   )

    if method != "GET":
        await send_error(HTTPStatus.NOT_FOUND)
        return

    if path == "/factorial":
        values = query_params.get("n")
        if values is None:
            await send_error(HTTPStatus.UNPROCESSABLE_ENTITY)
            return
        try:
            n = int(values[0])
        except (ValueError, TypeError):
            await send_error(HTTPStatus.UNPROCESSABLE_ENTITY)
            return
        if n < 0:
            await send_error(HTTPStatus.BAD_REQUEST)
            return
        await send_json(HTTPStatus.OK, {"result": math.factorial(n)})
        return

    if path.startswith("/fibonacci"):
        suffix = path[len("/fibonacci"):]
        if not suffix.startswith("/") or len(suffix) < 2:
            await send_error(HTTPStatus.UNPROCESSABLE_ENTITY)
            return
        raw = suffix[1:]
        try:
            n = int(raw)
        except (ValueError, TypeError):
            await send_error(HTTPStatus.UNPROCESSABLE_ENTITY)
            return
        if n < 0:
            await send_error(HTTPStatus.BAD_REQUEST)
            return
        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b
        await send_json(HTTPStatus.OK, {"result": b})
        return

    if path == "/mean":
        if not body:
            await send_error(HTTPStatus.UNPROCESSABLE_ENTITY)
            return
        try:
            data = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            await send_error(HTTPStatus.UNPROCESSABLE_ENTITY)
            return
        if not isinstance(data, list):
            await send_error(HTTPStatus.UNPROCESSABLE_ENTITY)
            return
        for item in data:
            if isinstance(item, bool) or not isinstance(item, (int, float)):
                await send_error(HTTPStatus.UNPROCESSABLE_ENTITY)
                return
        if len(data) == 0:
            await send_error(HTTPStatus.BAD_REQUEST)
            return
        result = sum(data) / len(data)
        await send_json(HTTPStatus.OK, {"result": result})
        return

    await send_error(HTTPStatus.NOT_FOUND)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
