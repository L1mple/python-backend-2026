import json
from http import HTTPStatus
from typing import Any, Awaitable, Callable


async def _send_json(
    send: Callable[[dict[str, Any]], Awaitable[None]],
    status_code: int,
    payload: dict[str, Any] | None = None,
) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    body = json.dumps(payload if not None else {"result": None}).encode("utf-8")
    await send(
        {
            "type": "http.response.body",
            "body": body,
        }
    )


async def _parse_body(
    receive: Callable[[], Awaitable[dict[str, Any]]],
) -> bytes:
    body = b""
    more_body = True
    while more_body:
        message = await receive()
        body += message.get("body", b"")
        more_body = message.get("more_body", False)
    return body


def _parse_n(raw: str | None) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _factorial(n: int) -> int:
    if n == 0:
        return 1
    result = 1
    for i in range(1, n + 1):
        result *= i
    return result


def _fibonacci(n: int) -> int:
    if n == 0:
        return 0
    if n == 1:
        return 1
    a, b = 0, 1
    for _ in range(1, n):
        a, b = b, a + b
    return b


async def _handle_factorial(
    scope: dict[str, Any],
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    query_string = scope.get("query_string", b"").decode("utf-8")
    params = {}
    for item in query_string.split("&"):
        if not item:
            continue
        key, _, value = item.partition("=")
        params[key] = value

    raw = params.get("n")
    n = _parse_n(raw)
    if n is None:
        await _send_json(send, HTTPStatus.UNPROCESSABLE_ENTITY)
        return
    if n < 0:
        await _send_json(send, HTTPStatus.BAD_REQUEST)
        return
    await _send_json(send, HTTPStatus.OK, {"result": _factorial(n)})


async def _handle_fibonacci(
    path_params: dict[str, str],
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    raw = path_params.get("n")
    n = _parse_n(raw)
    if n is None:
        await _send_json(send, HTTPStatus.UNPROCESSABLE_ENTITY)
        return
    if n < 0:
        await _send_json(send, HTTPStatus.BAD_REQUEST)
        return
    await _send_json(send, HTTPStatus.OK, {"result": _fibonacci(n)})


async def _handle_mean(
    scope: dict[str, Any],
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    body = await _parse_body(receive)
    if not body:
        await _send_json(send, HTTPStatus.UNPROCESSABLE_ENTITY)
        return
    try:
        data = json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        await _send_json(send, HTTPStatus.UNPROCESSABLE_ENTITY)
        return
    if not isinstance(data, list):
        await _send_json(send, HTTPStatus.UNPROCESSABLE_ENTITY)
        return
    if not data:
        await _send_json(send, HTTPStatus.BAD_REQUEST)
        return
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in data):
        await _send_json(send, HTTPStatus.UNPROCESSABLE_ENTITY)
        return
    await _send_json(send, HTTPStatus.OK, {"result": sum(data) / len(data)})


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
                await send({"type": "lifespan.startup"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown"})
                return

    if scope["type"] != "http":
        return

    method = scope["method"]
    path = scope["path"]

    if method == "GET" and path == "/factorial":
        await _handle_factorial(scope, send)
        return

    if method == "GET" and path.startswith("/fibonacci/"):
        raw = path[len("/fibonacci/"):]
        await _handle_fibonacci({"n": raw}, send)
        return

    if method == "GET" and path == "/mean":
        await _handle_mean(scope, receive, send)
        return

    await _send_json(send, HTTPStatus.NOT_FOUND, {"result": None})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
