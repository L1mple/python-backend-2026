from http import HTTPStatus
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs
import json
import math


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
                await send({
                    "type": "lifespan.startup.complete",
                })
            elif message["type"] == "lifespan.shutdown":
                await send({
                    "type": "lifespan.shutdown.complete",
                })
                return

    elif scope["type"] != "http":
        return
    

    method = scope["method"]
    path = scope["path"]

    status = HTTPStatus.OK
    result = None

    if method == "GET" and path == "/factorial":
        query_string = scope.get("query_string", b"").decode()
        query = parse_qs(query_string)

        if "n" not in query or not query["n"] or query["n"][0] == "":
            status = HTTPStatus.UNPROCESSABLE_ENTITY
        else:
            try:
                n = int(query["n"][0])
            except (ValueError, TypeError):
                status = HTTPStatus.UNPROCESSABLE_ENTITY
            else:
                if n < 0:
                    status = HTTPStatus.BAD_REQUEST
                else:
                    result = math.factorial(n)

    elif method == "GET" and path.startswith("/fibonacci/"):
        value = path[len("/fibonacci/"):]

        try:
            n = int(value)
        except (ValueError, TypeError):
            status = HTTPStatus.UNPROCESSABLE_ENTITY
        else:
            if n < 0:
                status = HTTPStatus.BAD_REQUEST
            else:
                a, b = 0, 1
                for _ in range(n):
                    a, b = b, a + b
                result = a

    elif method == "GET" and path == "/mean":
        body = b""

        while True:
            message = await receive()

            if message["type"] != "http.request":
                continue

            body += message.get("body", b"")

            if not message.get("more_body", False):
                break

        try:
            data = json.loads(body.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            status = HTTPStatus.UNPROCESSABLE_ENTITY
        else:
            if data is None:
                status = HTTPStatus.UNPROCESSABLE_ENTITY
            elif not isinstance(data, list):
                status = HTTPStatus.BAD_REQUEST
            elif len(data) == 0:
                status = HTTPStatus.BAD_REQUEST
            elif not all(
                isinstance(x, (int, float)) and not isinstance(x, bool)
                for x in data
            ):
                status = HTTPStatus.BAD_REQUEST
            else:
                result = sum(data) / len(data)

    else:
        status = HTTPStatus.NOT_FOUND

    if status == HTTPStatus.OK:
        response_body = json.dumps({"result": result}).encode()
    else:
        response_body = json.dumps({"error": status.phrase}).encode()

    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
            ],
        }
    )

    await send(
        {
            "type": "http.response.body",
            "body": response_body,
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)

