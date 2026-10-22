from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs

import json
import math

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
                await send(
                    {
                        "type": "lifespan.startup.complete",
                    }
                )

            elif message["type"] == "lifespan.shutdown":
                await send(
                    {
                        "type": "lifespan.shutdown.complete",
                    }
                )
                return

    path = scope["path"]

    if path == "/factorial":
        query_params = parse_qs(
            scope["query_string"].decode(),
            keep_blank_values=True,
        )

        try:
            n = int(query_params["n"][0])
        except (KeyError, ValueError):
            await send(
                {
                    "type": "http.response.start",
                    "status": 422,
                    "headers": [(b"content-type", b"application/json")],
                }
            )

            await send(
                {
                    "type": "http.response.body",
                    "body": b"",
                }
            )

            return

        if n < 0:
            body = json.dumps(
                {"detail": "Invalid value for n, must be non-negative"}
            ).encode()

            await send(
                {
                    "type": "http.response.start",
                    "status": 400,
                    "headers": [(b"content-type", b"application/json")],
                }
            )

            await send(
                {
                    "type": "http.response.body",
                    "body": body,
                }
            )

            return

        result = math.factorial(n)
        body = json.dumps({"result": result}).encode()

        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )

        await send(
            {
                "type": "http.response.body",
                "body": body,
            }
        )

    elif path.startswith("/fibonacci/"):
        try:
            n = int(path.split("/")[-1])
        except ValueError:
            await send(
                {
                    "type": "http.response.start",
                    "status": 422,
                    "headers": [(b"content-type", b"application/json")],
                }
            )

            await send(
                {
                    "type": "http.response.body",
                    "body": b"",
                }
            )

            return

        if n < 0:
            body = json.dumps(
                {"detail": "Invalid value for n, must be non-negative"}
            ).encode()

            await send(
                {
                    "type": "http.response.start",
                    "status": 400,
                    "headers": [(b"content-type", b"application/json")],
                }
            )

            await send(
                {
                    "type": "http.response.body",
                    "body": body,
                }
            )

            return

        a, b = 0, 1

        for _ in range(n):
            a, b = b, a + b

        body = json.dumps({"result": b}).encode()

        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )

        await send(
            {
                "type": "http.response.body",
                "body": body,
            }
        )

    elif path == "/mean":
        body = b""

        while True:
            message = await receive()
            body += message.get("body", b"")

            if not message.get("more_body", False):
                break

        data = json.loads(body)

        if data is None:
            await send(
                {
                    "type": "http.response.start",
                    "status": 422,
                    "headers": [(b"content-type", b"application/json")],
                }
            )

            await send(
                {
                    "type": "http.response.body",
                    "body": b"",
                }
            )

            return

        if len(data) == 0:
            body = json.dumps(
                {
                    "detail": (
                        "Invalid value for body, "
                        "must be non-empty array of floats"
                    )
                }
            ).encode()

            await send(
                {
                    "type": "http.response.start",
                    "status": 400,
                    "headers": [(b"content-type", b"application/json")],
                }
            )

            await send(
                {
                    "type": "http.response.body",
                    "body": body,
                }
            )

            return

        result = sum(data) / len(data)
        body = json.dumps({"result": result}).encode()

        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )

        await send(
            {
                "type": "http.response.body",
                "body": body,
            }
        )

    else:
        await send(
            {
                "type": "http.response.start",
                "status": 404,
                "headers": [(b"content-type", b"application/json")],
            }
        )

        await send(
            {
                "type": "http.response.body",
                "body": b"",
            }
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:application",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )