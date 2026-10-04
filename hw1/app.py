from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs
import math
import json

def handle_factorial(query_params):
    n = query_params.get('n', [''])[0]
    try:
        n = int(n)
    except ValueError:
        return 422, f"n is not a number: {n}"
    if n < 0:
        return 400, "Negative n: {n}"
    return 200, json.dumps({"result": math.factorial(n)})

def handle_fibonacci(path):
    path_parts = path.split("/")
    n = path_parts[2] if len(path_parts) == 3 else ""
    try:
        n = int(n)
    except ValueError:
        return 422, f"n is not a number: {n}"
    if n < 0:
        return 400, f"Negative n: {n}"
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return 200, json.dumps({"result": a})

def handle_mean(body):
    numbers = json.loads(body) if body else None
    if numbers is None:
        return 422, "numbers are required"
    elif numbers == []:
        return 400, "empty list"
    else:
        result = sum(numbers) / len(numbers)
        return 200, json.dumps({"result": result})

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

    if scope['type'] == 'lifespan':
        while True:
            message = await receive()
            if message['type'] == 'lifespan.startup':
                await send({'type': 'lifespan.startup.complete'})
            elif message['type'] == 'lifespan.shutdown':
                await send({'type': 'lifespan.shutdown.complete'})
                return

    path = scope['path']
    query_params = parse_qs(scope['query_string'].decode())

    status = 200
    response = ""

    try:
        if path == "/factorial":
            status, response = handle_factorial(query_params)
        elif path.startswith("/fibonacci"):
            status, response = handle_fibonacci(path)
        elif path == "/mean":
            body = b""
            more_body = True
            while more_body:
                message = await receive()
                body += message.get("body", b"")
                more_body = message.get("more_body", False)
            status, response = handle_mean(body)
        else:
            status = 404
            response = f"Invalid path: {path}"

    except Exception as e:
        status = 400
        response = f"Error: {str(e)}"

    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            [b"content-type", b"application/json"]
        ],
    })

    await send({"type": "http.response.body", "body": response.encode("utf-8"),
    })



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
