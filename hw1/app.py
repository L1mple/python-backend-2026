import json
import math
from enum import Enum
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs

class Endpoints(str, Enum):
    FACTORIAL = "/factorial"
    MEAN = "/mean"
    FIBONACCI = "/fibonacci"

class Methods(str, Enum):
    GET = "GET"
    POST = "POST"


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
                return None

    async def respond(status: int, data: Any = None):
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json")],
        })
        await send({"type": "http.response.body", "body": json.dumps(data).encode()})

    method = scope["method"]
    path = scope["path"]
    query = parse_qs(scope["query_string"].decode())

    if method != Methods.GET:
        return await respond(404)

    if path == Endpoints.FACTORIAL:
        try:
            n = int(query["n"][0])
        except (KeyError, ValueError):
            return await respond(422)
        if n < 0:
            return await respond(400)
        return await respond(200, {"result": math.factorial(n)})

    elif path.startswith(Endpoints.FIBONACCI):
        try:
            n = int(path.removeprefix("/fibonacci/"))
        except ValueError:
            return await respond(422)
        if n < 0:
            return await respond(400)
        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b
        return await respond(200, {"result": a})

    elif path == Endpoints.MEAN:
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body"):
                break
        try:
            if body:
                numbers = json.loads(body)
            else:
                numbers = [float(x) for x in query["numbers"][0].split(",")]
            if not isinstance(numbers, list):
                raise ValueError
            numbers = [float(x) for x in numbers]
        except (KeyError, ValueError, TypeError):
            return await respond(422)
        if not numbers:
            return await respond(400)
        return await respond(200, {"result": sum(numbers) / len(numbers)})
    else:
        return await respond(404)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
