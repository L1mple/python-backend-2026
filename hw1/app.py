import json
import math
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs


async def send_json(
    send: Callable[[dict[str, Any]], Awaitable[None]],
    status_code: int,
    data: dict[str, Any],
) -> None:
    body = json.dumps(data).encode("utf-8")

    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )

    await send({"type": "http.response.body", "body": body})


async def read_body(
    receive: Callable[[], Awaitable[dict[str, Any]]],
) -> bytes:
    body = b""

    while True:
        chunk = await receive()
        if chunk['type'] == "http.disconnect":
            break

        body += chunk.get("body", b"")
        if not chunk.get("more_body", False):
            break

    return body

def fibonacci(n: int) -> int:
    a = 0
    b = 1

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
                await send({
                    "type": "lifespan.startup.complete"
                })

            elif message["type"] == "lifespan.shutdown":
                await send({
                    "type": "lifespan.shutdown.complete"
                })
                return

    if scope['type'] != "http":
        return

    method = scope['method']
    path = scope['path']

    is_factorial = path == "/factorial"
    is_mean = path == "/mean"
    is_fibonacci = path.startswith("/fibonacci/")
    if not (is_factorial or is_fibonacci or is_mean):
        await send_json(send, 404, {"error": "Not found"})
        return
    
    if method != "GET":
        await send_json(send, 422, {"error": "Unsupported method"})
        return

    if is_factorial:
        query_string = scope['query_string']
        query_params = parse_qs(query_string.decode("utf-8"))

        if "n" not in query_params:
            await send_json(send, 422, {"error": "Invalid parameter n"})
            return
        
        try:
            n = int(query_params["n"][0])
        except (TypeError, ValueError):
            await send_json(
                send,
                422,
                {"error": "n must be an integer"},
            )
            return
        
        if n < 0:
            await send_json(send, 400, {"error": "Invalid parameter n"})
            return

        res = math.factorial(n)
        await send_json(send, 200, {"result": res})
        return

    if is_fibonacci:
        path_string = path.split("/")[-1]
        
        try:
            n = int(path_string)
        except (TypeError, ValueError):
            await send_json(
                send,
                422,
                {"error": "n must be an integer"},
            )
            return

        if n < 0:
            await send_json(send, 400, {"error": "n must be non-negative"})
            return

        res = fibonacci(n)
        await send_json(send, 200, {"result": res})
        return

    if is_mean:
        body = await read_body(receive)

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            await send_json(send, 422, {"error": "Invalid JSON"})
            return

        if data is None:
            await send_json(send, 422, {"error": "JSON body is required"})
            return

        if not isinstance(data, list):
            await send_json(send, 422, {"error": "JSON body must be a list"})
            return

        if len(data) == 0:
            await send_json(send, 400, {"error": "JSON body must not be empty"})
            return

        for item in data:
            if isinstance(item, bool) or not isinstance(item, (int, float)):
                await send_json(
                    send,
                    422,
                    {"error": "JSON body must contain only numbers"},
                )
                return

        res = sum(data)/len(data)

        await send_json(send, 200, {"result": res})
        return

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
