import json
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs


async def send_json(send: Callable[[dict[str, Any]], Awaitable[None]], status: int, payload: dict[str, Any]) -> None:
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


async def read_body(receive: Callable[[], Awaitable[dict[str, Any]]]) -> bytes:
    body = b""
    while True:
        message = await receive()
        body += message.get("body", b"")
        if not message.get("more_body", False):
            break
    return body


async def handle_factorial(scope: dict[str, Any], send: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
    query = parse_qs(scope["query_string"].decode("utf-8"))
    n_values = query.get("n")

    if not n_values or n_values[0] == "":
        await send_json(send, 422, {"error": "n is required"})
        return

    try:
        n = int(n_values[0])
    except ValueError:
        await send_json(send, 422, {"error": "n must be an integer"})
        return

    if n < 0:
        await send_json(send, 400, {"error": "n must be non-negative"})
        return

    result = 1
    for i in range(2, n + 1):
        result *= i

    await send_json(send, 200, {"result": result})


async def handle_fibonacci(n_raw: str, send: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
    try:
        n = int(n_raw)
    except ValueError:
        await send_json(send, 422, {"error": "n must be an integer"})
        return

    if n < 0:
        await send_json(send, 400, {"error": "n must be non-negative"})
        return

    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b

    await send_json(send, 200, {"result": a})


async def handle_mean(
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    raw_body = await read_body(receive)

    if not raw_body:
        await send_json(send, 422, {"error": "body is required"})
        return

    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError:
        await send_json(send, 422, {"error": "invalid json"})
        return

    if data is None or not isinstance(data, list):
        await send_json(send, 422, {"error": "body must be a list of numbers"})
        return

    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in data):
        await send_json(send, 422, {"error": "all items must be numbers"})
        return

    if len(data) == 0:
        await send_json(send, 400, {"error": "list must not be empty"})
        return

    result = sum(data) / len(data)

    await send_json(send, 200, {"result": result})


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

    assert scope["type"] == "http"

    method = scope["method"]
    path = scope["path"]

    if method == "GET" and path == "/factorial":
        await handle_factorial(scope, send)
        return

    if method == "GET" and path.startswith("/fibonacci/"):
        n_raw = path[len("/fibonacci/"):]
        await handle_fibonacci(n_raw, send)
        return

    if method == "GET" and path == "/mean":
        await handle_mean(receive, send)
        return

    await send_json(send, 404, {"error": "not found"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)