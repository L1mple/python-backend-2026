import json
import math
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs


async def send_json(send, status: int, data: dict) -> None:
    body = json.dumps(data).encode()
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [[b"content-type", b"application/json"]],
    })
    await send({
        "type": "http.response.body",
        "body": body,
    })


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

    chunks = []
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            break
        if message["type"] != "http.request":
            continue
        chunks.append(message.get("body", b""))
        if not message.get("more_body", False):
            break
    body = b"".join(chunks)

    if scope["method"] != "GET":
        await send_json(send, 404, {"error": "not found"})
        return

    path = scope["path"]
    query = parse_qs(scope.get("query_string", b"").decode(), keep_blank_values=True)

    if path == "/factorial":
        values = query.get("n")
        if not values or len(values) != 1:
            await send_json(send, 422, {"error": "n must be an integer"})
            return
        try:
            n = int(values[0])
        except ValueError:
            await send_json(send, 422, {"error": "n must be an integer"})
            return
        if n < 0:
            await send_json(send, 400, {"error": "n must be >= 0"})
            return
        await send_json(send, 200, {"result": math.factorial(n)})
        return

    if path.startswith("/fibonacci/"):
        raw_n = path[len("/fibonacci/"):]
        if "/" in raw_n:
            await send_json(send, 404, {"error": "not found"})
            return
        try:
            n = int(raw_n)
        except ValueError:
            await send_json(send, 422, {"error": "n must be an integer"})
            return
        if n < 0:
            await send_json(send, 400, {"error": "n must be >= 0"})
            return
        await send_json(send, 200, {"result": fibonacci(n)})
        return

    if path == "/mean":
        if body.strip():
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                await send_json(send, 422, {"error": "invalid json"})
                return
            if not isinstance(data, list):
                await send_json(send, 422, {"error": "expected a list of numbers"})
                return
            numbers = data
        else:
            raw_numbers = query.get("numbers")
            if not raw_numbers:
                await send_json(send, 422, {"error": "numbers are required"})
                return
            numbers = []
            for piece in ",".join(raw_numbers).split(","):
                piece = piece.strip()
                try:
                    if "." in piece or "e" in piece.lower():
                        numbers.append(float(piece))
                    else:
                        numbers.append(int(piece))
                except ValueError:
                    await send_json(send, 422, {"error": "numbers must be numeric"})
                    return

        if not numbers:
            await send_json(send, 400, {"error": "list must not be empty"})
            return
        for item in numbers:
            if type(item) not in (int, float):
                await send_json(send, 422, {"error": "list must contain only numbers"})
                return

        await send_json(send, 200, {"result": sum(numbers) / len(numbers)})
        return

    await send_json(send, 404, {"error": "not found"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
