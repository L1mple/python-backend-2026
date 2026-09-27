import json
import math
from http import HTTPStatus
from typing import Any, Awaitable, Callable  # noqa: UP035
from urllib.parse import parse_qs


async def send_json(send, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode()
    await send(
        {
            "type": "http.response.start",
            "status": int(status),
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", str(len(body)).encode()],
            ],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": body,
            "more_body": False,
        }
    )


async def read_body(receive) -> bytes:
    body = b""
    while True:
        message = await receive()
        if message.get("type") == "http.disconnect":
            break
        body += message.get("body", b"")
        if not message.get("more_body", False):
            break
    return body


async def application(
    scope: dict[str, Any],
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
):
    scope_type = scope.get("type")

    if scope_type == "lifespan":
        while True:
            message = await receive()
            if message.get("type") == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message.get("type") == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return

    if scope_type != "http":
        return

    method = scope.get("method", "").upper()
    if method != "GET":
        await send_json(send, HTTPStatus.NOT_FOUND, {"detail": "Not Found"})
        return

    path = scope.get("path", "").split("?", 1)[0]

    query_string = scope.get("query_string") or b""
    if isinstance(query_string, bytes):
        query_string = query_string.decode(errors="replace")

    query = parse_qs(query_string, keep_blank_values=True)

    if path == "/factorial":
        values = query.get("n", [])
        try:
            n = int(values[0])
        except (IndexError, ValueError):
            await send_json(
                send,
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"detail": "Invalid query parameter n"},
            )
            return

        if n < 0:
            await send_json(
                send,
                HTTPStatus.BAD_REQUEST,
                {"detail": "Invalid value for n, must be non-negative"},
            )
            return

        await send_json(send, HTTPStatus.OK, {"result": math.factorial(n)})
        return

    if path.startswith("/fibonacci/"):
        raw_n = path[len("/fibonacci/"):]

        if not raw_n or "/" in raw_n:
            await send_json(send, HTTPStatus.NOT_FOUND, {"detail": "Not Found"})
            return

        try:
            n = int(raw_n)
        except ValueError:
            await send_json(
                send,
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"detail": "Invalid path parameter n"},
            )
            return

        if n < 0:
            await send_json(
                send,
                HTTPStatus.BAD_REQUEST,
                {"detail": "Invalid value for n, must be non-negative"},
            )
            return

        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b

        await send_json(send, HTTPStatus.OK, {"result": b})
        return

    if path == "/mean":
        body = await read_body(receive)

        if not body:
            await send_json(
                send,
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"detail": "Invalid request body"},
            )
            return

        try:
            data = json.loads(body)
        except ValueError:
            await send_json(
                send,
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"detail": "Invalid request body"},
            )
            return

        if not isinstance(data, list):
            await send_json(
                send,
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"detail": "Invalid request body"},
            )
            return

        if not data:
            await send_json(
                send,
                HTTPStatus.BAD_REQUEST,
                {"detail": "Invalid value for body, must be non-empty array of floats"},
            )
            return

        for value in data:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                await send_json(
                    send,
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    {"detail": "Invalid request body"},
                )
                return

        await send_json(send, HTTPStatus.OK, {"result": sum(data) / len(data)})
        return

    await send_json(send, HTTPStatus.NOT_FOUND, {"detail": "Not Found"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)