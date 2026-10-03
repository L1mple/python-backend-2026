import json
from http import HTTPStatus
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qsl


async def _read_body(
    receive: Callable[[], Awaitable[dict[str, Any]]],
) -> bytes:
    body = b""
    while True:
        message = await receive()
        if message["type"] != "http.request":
            break
        body += message.get("body", b"")
        if not message.get("more_body", False):
            break
    return body


async def _send_json(
    send: Callable[[dict[str, Any]], Awaitable[None]],
    status: int,
    payload: Any,
) -> None:
    body = json.dumps(payload).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": body,
        }
    )


async def _handle_factorial(query, send):
    if "n" not in query:
        await _send_json(
            send,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {"detail": "'n' query parameter is required"},
        )
        return

    try:
        n = int(query["n"])
    except (TypeError, ValueError):
        await _send_json(
            send,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {"detail": "'n' must be an integer"},
        )
        return

    if n < 0:
        await _send_json(
            send,
            HTTPStatus.BAD_REQUEST,
            {"detail": "'n' must be non-negative"},
        )
        return

    result = 1
    for i in range(2, n + 1):
        result *= i

    await _send_json(send, HTTPStatus.OK, {"result": result})


async def _handle_fibonacci(n_str: str, send):
    try:
        n = int(n_str)
    except (TypeError, ValueError):
        await _send_json(
            send,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {"detail": "'n' must be an integer"},
        )
        return

    if n < 0:
        await _send_json(
            send,
            HTTPStatus.BAD_REQUEST,
            {"detail": "'n' must be non-negative"},
        )
        return

    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b

    await _send_json(send, HTTPStatus.OK, {"result": a})


async def _handle_mean(body: bytes, send):
    if not body:
        await _send_json(
            send,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {"detail": "request body is required"},
        )
        return

    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        await _send_json(
            send,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {"detail": "request body must be valid JSON"},
        )
        return

    if not isinstance(data, list):
        await _send_json(
            send,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {"detail": "request body must be a JSON array"},
        )
        return

    if len(data) == 0:
        await _send_json(
            send,
            HTTPStatus.BAD_REQUEST,
            {"detail": "array must not be empty"},
        )
        return

    for x in data:
        if isinstance(x, bool) or not isinstance(x, (int, float)):
            await _send_json(
                send,
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"detail": "all array elements must be numbers"},
            )
            return

    result = sum(data) / len(data)
    await _send_json(send, HTTPStatus.OK, {"result": result})


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
        return

    if scope["type"] != "http":
        return

    method = scope["method"]
    path = scope["path"]
    query = dict(
        parse_qsl(scope["query_string"].decode("utf-8"), keep_blank_values=True)
    )

    if method == "GET" and path == "/factorial":
        await _handle_factorial(query, send)
    elif method == "GET" and path.startswith("/fibonacci/"):
        await _handle_fibonacci(path[len("/fibonacci/") :], send)
    elif method == "GET" and path == "/mean":
        body = await _read_body(receive)
        await _handle_mean(body, send)
    else:
        await _send_json(send, HTTPStatus.NOT_FOUND, {"detail": "Not Found"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
