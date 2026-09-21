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
        await receive()
        await send({"type": "lifespan.startup.complete"})

        await receive()
        await send({"type": "lifespan.shutdown.complete"})
        return

    status = 404
    response = {"error": "Not Found"}

    if scope["method"] == "GET" and scope["path"] == "/factorial":
        query = parse_qs(scope["query_string"].decode("utf-8"), keep_blank_values=True)

        n_values = query.get("n")

        if n_values is None or len(n_values) != 1:
            status = 422
            response = {"error": "Parameter 'n' is required"}
        else:
            try:
                n = int(n_values[0])
            except ValueError:
                status = 422
                response = {"error": "Invalid value for n"}
            else:
                if n < 0:
                    status = 400
                    response = {"error": "n must be a non-negative integer"}
                else:
                    result = math.factorial(n)
                    status = 200
                    response = {"result": result}

    elif scope["method"] == "GET" and scope["path"].startswith("/fibonacci/"):
        n_text = scope["path"].removeprefix("/fibonacci/")

        try:
            n = int(n_text)
        except ValueError:
            status = 422
            response = {"error": "Invalid value for n"}
        else:
            if n < 0:
                status = 400
                response = {"error": "n must be a non-negative integer"}
            else:
                a, b = 0, 1
                for _ in range(n):
                    a, b = b, a + b
                status = 200
                response = {"result": b}

    elif scope["method"] == "GET" and scope["path"] == "/mean":
        message = await receive()
        request_body = message.get("body", b"")

        try:
            data = json.loads(request_body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            status = 422
            response = {"error": "Invalid request body"}
        else:
            if not isinstance(data, list):
                status = 422
                response = {"error": "Request body must be a list"}
            elif len(data) == 0:
                status = 400
                response = {"error": "List of numbers cannot be empty"}
            elif not all(type(value) in (int, float) for value in data):
                status = 422
                response = {"error": "All elements in the list must be numbers"}
            else:
                result = sum(data)/len(data)
                status = 200
                response = {"result": result}

    body = json.dumps(response).encode("utf-8")

    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [[b"content-type", b"application/json"]],
    })
    await send({
        "type": "http.response.body",
        "body": body,
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
