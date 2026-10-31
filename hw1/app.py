from typing import Any, Awaitable, Callable
import json
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

    method = scope["method"]
    path = scope["path"]

    status = 404
    result = None

    if method == "GET" and path.startswith("/fibonacci/"):
        value = path.split("/")[-1]

        try:
            n = int(value)
        except ValueError:
            status = 422
        else:
            if n < 0:
                status = 400
            else:
                a, b = 0, 1
                for _ in range(n):
                    a, b = b, a + b

                result = a
                status = 200

    elif method == "GET" and path == "/factorial":
        query = parse_qs(scope["query_string"].decode())
        value = query.get("n", [None])[0]

        try:
            n = int(value)
        except (TypeError, ValueError):
            status = 422
        else:
            if n < 0:
                status = 400
            else:
                result = 1

                for i in range(2, n + 1):
                    result *= i

                status = 200

    elif method == "GET" and path == "/mean":
        body = b""

        while True:
            message = await receive()
            body += message.get("body", b"")

            if not message.get("more_body", False):
                break

        try:
            numbers = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            status = 422
        else:
            if numbers is None:
                status = 422
            elif not isinstance(numbers, list):
                status = 400
            elif not numbers:
                status = 400
            elif not all(
                    isinstance(x, (int, float)) and not isinstance(x, bool)
                    for x in numbers
            ):
                status = 400
            else:
                result = sum(numbers) / len(numbers)
                status = 200

    if status == 200:
        response = json.dumps({"result": result}).encode()
    else:
        response = b""

    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [[b"content-type", b"application/json"]],
    })

    await send({
        "type": "http.response.body",
        "body": response,
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
