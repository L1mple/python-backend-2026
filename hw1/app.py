import json
import math
from typing import Any, Awaitable, Callable
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
                break
        return

    if scope["type"] == "http":
        path = scope.get("path", "")
        query_string = scope.get("query_string", b"")

        if path.startswith("/fibonacci/"):
            await handle_fibonacci(path, send)
        elif path == "/factorial":
            await handle_factorial(query_string, send)
        elif path == "/mean":
            await handle_mean(receive, send)
        else:
            await handle_404(send)


async def send_response(send, status: int, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [(b"content-type", b"application/json")],
    })
    await send({
        "type": "http.response.body",
        "body": body,
    })


async def handle_fibonacci(path: str, send):
    rn = path.rsplit("/", 1)[-1]
    try:
        n = int(rn)
    except ValueError:
        await send_response(send, 422, {"error": "Unprocessable entity"})
        return

    if n < 0:
        await send_response(send, 400, {"error": "Number is negative"})
        return

    i, j = 0, 1
    for _ in range(n):
        i, j = j, i + j

    await send_response(send, 200, {"result": i})


async def handle_factorial(query: bytes, send):
    query_str = query.decode("utf-8")
    params = parse_qs(query_str)
    val = params.get("n")

    if not val or val[0] == "":
        await send_response(send, 422, {"error": "Missing parameter n"})
        return

    try:
        n = int(val[0])
    except ValueError:
        await send_response(send, 422, {"error": "Invalid integer format"})
        return

    if n < 0:
        await send_response(send, 400, {"error": "Negative number"})
        return

    try:
        fact = math.factorial(n)
    except OverflowError:
        await send_response(send, 400, {"error": "Number too large"})
        return

    await send_response(send, 200, {"result": fact})


async def handle_mean(receive, send):
    body = b""
    more_body = True
    while more_body:
        message = await receive()
        body += message.get("body", b"")
        more_body = message.get("more_body", False)

    if not body:
        await send_response(send, 422, {"error": "Empty body"})
        return

    try:
        data = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        await send_response(send, 422, {"error": "Invalid JSON"})
        return

    if not isinstance(data, list):
        await send_response(send, 422, {"error": "JSON body must be a list"})
        return

    if len(data) == 0:
        await send_response(send, 400, {"error": "Empty list"})
        return

    try:
        numbers = [float(x) for x in data]
    except (ValueError, TypeError):
        await send_response(send, 422, {"error": "Array elements must be numbers"})
        return

    avg = sum(numbers) / len(numbers)
    await send_response(send, 200, {"result": avg})


async def handle_404(send):
    await send_response(send, 404, {"error": "Not Found"})
