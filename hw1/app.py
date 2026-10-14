import json
import math
from statistics import mean
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
    if scope["type"] == "lifespan":
        while True:
            event = await receive()
            if event["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif event["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return

    if scope["type"] != "http":
        return

    async def respond(status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, allow_nan=False).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    path = scope["path"]
    is_fibonacci = path.startswith("/fibonacci/") and path.count("/") == 2
    if path not in ("/factorial", "/mean") and not is_fibonacci:
        await respond(404, {"error": "Endpoint not found"})
        return

    if scope["method"] != "GET":
        await respond(422, {"error": "Only GET requests are supported"})
        return

    if path == "/factorial" or is_fibonacci:
        try:
            if path == "/factorial":
                query = parse_qs(scope.get("query_string", b"").decode("utf-8"))
                n = int(query["n"][0])
            else:
                n = int(path.rsplit("/", 1)[1])
        except (KeyError, IndexError, ValueError, UnicodeDecodeError):
            await respond(422, {"error": "n must be an integer"})
            return

        if n < 0:
            await respond(400, {"error": "n must be non-negative"})
            return

        if path == "/factorial":
            result = math.factorial(n)
        else:
            result, next_number = 0, 1
            for _ in range(n):
                result, next_number = next_number, result + next_number
    else:
        body = bytearray()
        while True:
            event = await receive()
            if event["type"] == "http.disconnect":
                return
            body.extend(event.get("body", b""))
            if not event.get("more_body", False):
                break

        try:
            numbers = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            await respond(422, {"error": "Body must be a JSON array of numbers"})
            return

        if not isinstance(numbers, list) or any(
            type(number) not in (int, float)
            or (isinstance(number, float) and not math.isfinite(number))
            for number in numbers
        ):
            await respond(422, {"error": "Body must be a JSON array of finite numbers"})
            return
        if not numbers:
            await respond(400, {"error": "The array must not be empty"})
            return

        try:
            result = mean(numbers)
        except OverflowError:
            await respond(400, {"error": "Mean is outside the supported numeric range"})
            return

    await respond(200, {"result": result})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
