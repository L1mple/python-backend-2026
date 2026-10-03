from typing import Any, Awaitable, Callable
import json
from urllib.parse import parse_qs


async def application(
    scope: dict[str, Any],
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
):
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

    if path.startswith("/fibonacci/"):
        if method != "GET":
            return await send_json(send, 422, {"detail": "Method not allowed"})
        try:
            n = int(path.split("/")[-1])
        except ValueError:
            return await send_json(send, 422, {"detail": "Invalid parameter"})

        if n < 0:
            return await send_json(send, 400, {"detail": "Negative not allowed"})

        return await send_json(send, 200, {"result": fibonacci(n)})

    if path == "/factorial":
        if method != "GET":
            return await send_json(send, 422, {"detail": "Method not allowed"})
        query_string = scope.get("query_string", b"").decode()
        query = parse_qs(query_string)
        n = query.get("n", [None])[0]
        if not n:
            return await send_json(send, 422, {"detail": "Missing or empty n"})
        try:
            n = int(n)
        except ValueError:
            return await send_json(send, 422, {"detail": "Invalid n"})

        if n < 0:
            return await send_json(send, 400, {"detail": "Negative not allowed"})

        return await send_json(send, 200, {"result": factorial(n)})

    if path == "/mean":
        if method != "GET":
            return await send_json(send, 422, {"detail": "Method not allowed"})
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break
        if not body:
            return await send_json(send, 422, {"detail": "Empty body"})

        try:
            numbers = json.loads(body)
        except json.JSONDecodeError:
            return await send_json(send, 422, {"detail": "Invalid JSON"})

        if numbers is None:
            return await send_json(send, 422, {"detail": "Invalid body"})

        if not isinstance(numbers, list) or not numbers:
            return await send_json(send, 400, {"detail": "Body must be list"})

        try:
            numbers = [float(x) for x in numbers]
        except (TypeError, ValueError):
            return await send_json(send, 422, {"detail": "Invalid numbers"})

        return await send_json(
            send,
            200,
            {"result": sum(numbers) / len(numbers)},
        )

    await send_json(send, 404, {"detail": "Not found"})


async def send_json(send, status, data):
    body = json.dumps(data).encode()

    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ],
    })

    await send({
        "type": "http.response.body",
        "body": body,
    })


def fibonacci(n):
    a, b = 0, 1

    for _ in range(n):
        a, b = b, a + b

    return a


def factorial(n):
    result = 1

    for i in range(2, n + 1):
        result *= i

    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
