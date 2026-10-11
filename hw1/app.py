import json
import math
from http import HTTPStatus
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs


async def _send_json(
    send: Callable[[dict[str, Any]], Awaitable[None]],
    status: HTTPStatus,
    payload: dict[str, Any],
) -> None:
    body = json.dumps(payload).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status.value,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def _send_error(
    send: Callable[[dict[str, Any]], Awaitable[None]],
    status: HTTPStatus,
    detail: str,
) -> None:
    await _send_json(send, status, {"detail": detail})


async def _read_body(
    receive: Callable[[], Awaitable[dict[str, Any]]],
) -> bytes:
    chunks: list[bytes] = []

    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            return b""
        if message["type"] != "http.request":
            continue

        chunks.append(message.get("body", b""))
        if not message.get("more_body", False):
            return b"".join(chunks)


def _is_number(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, int | float)
        and (not isinstance(value, float) or math.isfinite(value))
    )


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

    if scope["type"] != "http" or scope.get("method") != "GET":
        await _send_error(send, HTTPStatus.NOT_FOUND, "Endpoint not found")
        return

    path = scope.get("path", "")

    if path == "/factorial":
        try:
            query = parse_qs(
                scope.get("query_string", b"").decode("utf-8"),
                keep_blank_values=True,
            )
            n = int(query["n"][-1])
        except (KeyError, UnicodeDecodeError, ValueError):
            await _send_error(
                send,
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "Query parameter n must be an integer",
            )
            return

        if n < 0:
            await _send_error(send, HTTPStatus.BAD_REQUEST, "n must be non-negative")
            return

        try:
            await _send_json(send, HTTPStatus.OK, {"result": math.factorial(n)})
        except (OverflowError, ValueError):
            await _send_error(send, HTTPStatus.BAD_REQUEST, "n is too large")
        return

    prefix = "/fibonacci/"
    if path.startswith(prefix):
        value = path.removeprefix(prefix)
        if not value or "/" in value:
            await _send_error(send, HTTPStatus.NOT_FOUND, "Endpoint not found")
            return

        try:
            n = int(value)
        except ValueError:
            await _send_error(
                send,
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "Path parameter n must be an integer",
            )
            return

        if n < 0:
            await _send_error(send, HTTPStatus.BAD_REQUEST, "n must be non-negative")
            return

        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b

        try:
            await _send_json(send, HTTPStatus.OK, {"result": b})
        except ValueError:
            await _send_error(send, HTTPStatus.BAD_REQUEST, "n is too large")
        return

    if path == "/mean":
        try:
            data = json.loads(await _read_body(receive))
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            await _send_error(
                send,
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "Body must be a JSON array of numbers",
            )
            return

        if not isinstance(data, list) or not all(_is_number(value) for value in data):
            await _send_error(
                send,
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "Body must be a JSON array of numbers",
            )
            return

        if not data:
            await _send_error(send, HTTPStatus.BAD_REQUEST, "Body must not be empty")
            return

        try:
            result = sum(data) / len(data)
        except OverflowError:
            await _send_error(send, HTTPStatus.BAD_REQUEST, "Mean is too large")
            return

        if not math.isfinite(result):
            await _send_error(send, HTTPStatus.BAD_REQUEST, "Mean is too large")
            return

        await _send_json(send, HTTPStatus.OK, {"result": result})
        return

    await _send_error(send, HTTPStatus.NOT_FOUND, "Endpoint not found")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
