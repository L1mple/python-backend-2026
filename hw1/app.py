import json
import math
from typing import Any, Awaitable, Callable


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
                    "type": "lifespan.startup.complete",
                })

            elif message["type"] == "lifespan.shutdown":
                await send({
                    "type": "lifespan.shutdown.complete",
                })
                return

    if scope["type"] != "http":
        return

    path = scope["path"]
    method = scope["method"]

    if path.startswith("/fibonacci/"):
        if method != "GET":
            body = json.dumps({
                "detail": "Unsupported request format"
            }).encode()

            await send({
                "type": "http.response.start",
                "status": 422,
                "headers": [
                    (b"content-type", b"application/json"),
                ],
            })

            await send({
                "type": "http.response.body",
                "body": body,
            })

            return

        n = path.removeprefix("/fibonacci/")

        try:
            n = int(n)
        except ValueError:
            body = json.dumps({
                "detail": "Invalid n"
            }).encode()

            await send({
                "type": "http.response.start",
                "status": 422,
                "headers": [
                    (b"content-type", b"application/json"),
                ],
            })

            await send({
                "type": "http.response.body",
                "body": body,
            })

            return

        if n < 0:
            body = json.dumps({
                "detail": "Invalid n"
            }).encode()

            await send({
                "type": "http.response.start",
                "status": 400,
                "headers": [
                    (b"content-type", b"application/json"),
                ],
            })

            await send({
                "type": "http.response.body",
                "body": body,
            })

            return

        a, b = 0, 1

        for _ in range(n):
            a, b = b, a + b

        body = json.dumps({
            "result": b
        }).encode()

        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"content-type", b"application/json"),
            ],
        })

        await send({
            "type": "http.response.body",
            "body": body,
        })

    elif path == "/factorial":
        if method != "GET":
            body = json.dumps({
                "detail": "Unsupported request format"
            }).encode()

            await send({
                "type": "http.response.start",
                "status": 422,
                "headers": [
                    (b"content-type", b"application/json"),
                ],
            })

            await send({
                "type": "http.response.body",
                "body": body,
            })

            return

        query = scope["query_string"].decode()

        if not query.startswith("n="):
            body = json.dumps({
                "detail": "Invalid n"
            }).encode()

            await send({
                "type": "http.response.start",
                "status": 422,
                "headers": [
                    (b"content-type", b"application/json"),
                ],
            })

            await send({
                "type": "http.response.body",
                "body": body,
            })

            return

        n = query.removeprefix("n=")

        try:
            n = int(n)
        except ValueError:
            body = json.dumps({
                "detail": "Invalid n"
            }).encode()

            await send({
                "type": "http.response.start",
                "status": 422,
                "headers": [
                    (b"content-type", b"application/json"),
                ],
            })

            await send({
                "type": "http.response.body",
                "body": body,
            })

            return

        if n < 0:
            body = json.dumps({
                "detail": "Invalid n"
            }).encode()

            await send({
                "type": "http.response.start",
                "status": 400,
                "headers": [
                    (b"content-type", b"application/json"),
                ],
            })

            await send({
                "type": "http.response.body",
                "body": body,
            })

            return

        result = math.factorial(n)

        body = json.dumps({
            "result": result
        }).encode()

        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"content-type", b"application/json"),
            ],
        })

        await send({
            "type": "http.response.body",
            "body": body,
        })

    elif path == "/mean":
        if method != "GET":
            body = json.dumps({
                "detail": "Unsupported request format"
            }).encode()

            await send({
                "type": "http.response.start",
                "status": 422,
                "headers": [
                    (b"content-type", b"application/json"),
                ],
            })

            await send({
                "type": "http.response.body",
                "body": body,
            })

            return

        message = await receive()
        raw_body = message.get("body", b"")

        if not raw_body:
            body = json.dumps({
                "detail": "Invalid input"
            }).encode()

            await send({
                "type": "http.response.start",
                "status": 422,
                "headers": [
                    (b"content-type", b"application/json"),
                ],
            })

            await send({
                "type": "http.response.body",
                "body": body,
            })

            return

        try:
            nums = json.loads(raw_body)
        except json.JSONDecodeError:
            body = json.dumps({
                "detail": "Invalid input"
            }).encode()

            await send({
                "type": "http.response.start",
                "status": 422,
                "headers": [
                    (b"content-type", b"application/json"),
                ],
            })

            await send({
                "type": "http.response.body",
                "body": body,
            })

            return

        if not isinstance(nums, list):
            body = json.dumps({
                "detail": "Invalid input"
            }).encode()

            await send({
                "type": "http.response.start",
                "status": 422,
                "headers": [
                    (b"content-type", b"application/json"),
                ],
            })

            await send({
                "type": "http.response.body",
                "body": body,
            })

            return

        if len(nums) == 0:
            body = json.dumps({
                "detail": "Invalid input"
            }).encode()

            await send({
                "type": "http.response.start",
                "status": 400,
                "headers": [
                    (b"content-type", b"application/json"),
                ],
            })

            await send({
                "type": "http.response.body",
                "body": body,
            })

            return

        result = sum(nums) / len(nums)

        body = json.dumps({
            "result": result
        }).encode()

        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"content-type", b"application/json"),
            ],
        })

        await send({
            "type": "http.response.body",
            "body": body,
        })

    else:
        body = json.dumps({
            "detail": "Not found"
        }).encode()

        await send({
            "type": "http.response.start",
            "status": 404,
            "headers": [
                (b"content-type", b"application/json"),
            ],
        })

        await send({
            "type": "http.response.body",
            "body": body,
        })



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
