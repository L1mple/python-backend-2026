import json
import math
from http import HTTPStatus
from statistics import mean
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs


async def send_json(send, status: int, data: dict[str, Any], headers=()):
    body = json.dumps(data, allow_nan=False).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                *headers,
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def handle_factorial(scope, receive, send):
    query = parse_qs(
        scope.get("query_string", b"").decode("utf-8"),
        keep_blank_values=True,
    )
    n = int(query.get("n", [""])[-1])
    if n < 0:
        await send_json(
            send, HTTPStatus.BAD_REQUEST, {"detail": "n must be non-negative"}
        )
        return

    await send_json(send, HTTPStatus.OK, {"result": math.factorial(n)})


async def handle_fibonacci(scope, receive, send):
    n = int(scope["path"].rsplit("/", 1)[1])
    if n < 0:
        await send_json(
            send, HTTPStatus.BAD_REQUEST, {"detail": "n must be non-negative"}
        )
        return

    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b

    await send_json(send, HTTPStatus.OK, {"result": b})


async def handle_mean(scope, receive, send):
    body = bytearray()
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            return
        body.extend(message.get("body", b""))
        if not message.get("more_body", False):
            break

    numbers = json.loads(body)
    if not isinstance(numbers, list) or any(
        type(number) not in (int, float) or not math.isfinite(number)
        for number in numbers
    ):
        raise ValueError

    if not numbers:
        await send_json(
            send,
            HTTPStatus.BAD_REQUEST,
            {"detail": "Body must be a non-empty array of numbers"},
        )
        return

    result = float(mean(numbers))
    if not math.isfinite(result):
        raise ValueError

    await send_json(send, HTTPStatus.OK, {"result": result})


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

    match scope["path"].split("/"):
        case ["", "factorial"]:
            handler = handle_factorial
        case ["", "fibonacci", n] if n:
            handler = handle_fibonacci
        case ["", "mean"]:
            handler = handle_mean
        case _:
            await send_json(send, HTTPStatus.NOT_FOUND, {"detail": "Not Found"})
            return

    if scope["method"] != "GET":
        await send_json(
            send,
            HTTPStatus.METHOD_NOT_ALLOWED,
            {"detail": "Method Not Allowed"},
            ((b"allow", b"GET"),),
        )
        return

    try:
        await handler(scope, receive, send)
    except (ValueError, OverflowError):
        await send_json(
            send,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {"detail": "Invalid request parameters"},
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
