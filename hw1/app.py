from typing import Any, Awaitable, Callable
import json
import math
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

    async def respond(status: int, data: dict[str, Any]) -> None:
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json")],
        })
        await send({"type": "http.response.body", "body": json.dumps(data).encode()})

    method = scope["method"]
    path = scope["path"]

    if method != "GET":
        await respond(404, {"error": "Not found"})
        return

    if path == "/factorial":
        params = parse_qs(scope["query_string"].decode())
        try:
            n = int(params["n"][0])
        except (KeyError, ValueError):
            await respond(422, {"error": "n must be an integer"})
            return
        if n < 0:
            await respond(400, {"error": "n must be non-negative"})
            return
        await respond(200, {"result": math.factorial(n)})
        return

    if path.startswith("/fibonacci/"):
        try:
            n = int(path.removeprefix("/fibonacci/"))
        except ValueError:
            await respond(422, {"error": "n must be an integer"})
            return
        if n < 0:
            await respond(400, {"error": "n must be non-negative"})
            return
        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b
        await respond(200, {"result": b})
        return

    if path == "/mean":
        body = b""
        more_body = True
        while more_body:
            message = await receive()
            body += message.get("body", b"")
            more_body = message.get("more_body", False)
        try:
            numbers = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            await respond(422, {"error": "body must be a JSON array"})
            return
        if not isinstance(numbers, list) or not all(
            isinstance(x, (int, float)) and not isinstance(x, bool) for x in numbers
        ):
            await respond(422, {"error": "body must be a JSON array of numbers"})
            return
        if not numbers:
            await respond(400, {"error": "array must not be empty"})
            return
        await respond(200, {"result": sum(numbers) / len(numbers)})
        return

    await respond(404, {"error": "Not found"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
