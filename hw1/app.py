import json
import math
from http import HTTPStatus
from urllib.parse import parse_qs
from typing import Any, Awaitable, Callable


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

    async def respond(status: HTTPStatus, payload: dict[str, Any]) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": status.value,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send(
            {
                "type": "http.response.body", 
                "body": json.dumps(payload).encode("utf-8")
            }
        )

    method = scope["method"]
    path = scope["path"]

    if method == "GET" and path == "/factorial":
        query = parse_qs(scope.get("query_string", b"").decode(), keep_blank_values=True)
        values = query.get("n")
        if not values or values[0] == "":
            await respond(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "n is required"})
            return

        try:
            n = int(values[0])
        except ValueError:
            await respond(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "n must be an integer"})
            return

        if n < 0:
            await respond(HTTPStatus.BAD_REQUEST, {"error": "n must be non-negative"})
            return

        await respond(HTTPStatus.OK, {"result": math.factorial(n)})
        return

    if method == "GET" and path.startswith("/fibonacci/"):
        raw_n = path[len("/fibonacci/") :]
        if raw_n and "/" not in raw_n:
            try:
                n = int(raw_n)
            except ValueError:
                await respond(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "n must be an integer"})
                return

            if n < 0:
                await respond(HTTPStatus.BAD_REQUEST, {"error": "n must be non-negative"})
                return

            a, b = 1, 0
            for _ in range(n):
                a, b = b, a + b

            await respond(HTTPStatus.OK, {"result": b})
            return

    if method == "GET" and path == "/mean":
        message = await receive()
        body = message.get("body", b"")

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            await respond(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "body must be a JSON array"})
            return

        is_number_list = isinstance(data, list) and all(
            isinstance(x, (int, float)) and not isinstance(x, bool) for x in data
        )
        if not is_number_list:
            await respond(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "body must be an array of numbers"})
            return

        if len(data) == 0:
            await respond(HTTPStatus.BAD_REQUEST, {"error": "array must be non-empty"})
            return

        await respond(HTTPStatus.OK, {"result": sum(data) / len(data)})
        return

    await respond(HTTPStatus.NOT_FOUND, {"error": "not found"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
