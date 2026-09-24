import json
import math
from http import HTTPStatus
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs

# Python can't turn ints with more than ~4300 digits into strings,
# so results must stay below that (and computing them stays cheap)
MAX_FACTORIAL_N = 1000
MAX_FIBONACCI_N = 10000
MAX_BODY_SIZE = 1024 * 1024


async def send_json(send, status: int, data: dict[str, Any]) -> None:
    body = json.dumps(data).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def send_error(send, status: HTTPStatus) -> None:
    await send_json(send, status, {"detail": status.phrase})


async def read_body(receive) -> bytes | None:
    """Returns None if the body is larger than MAX_BODY_SIZE."""
    body = b""
    more_body = True
    while more_body:
        message = await receive()
        body += message.get("body", b"")
        if len(body) > MAX_BODY_SIZE:
            return None
        more_body = message.get("more_body", False)
    return body


async def handle_lifespan(receive, send) -> None:
    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif message["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return


def fibonacci(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


async def handle_factorial(scope, send) -> None:
    query = parse_qs(scope["query_string"].decode(), keep_blank_values=True)
    values = query.get("n")
    if not values:
        return await send_error(send, HTTPStatus.UNPROCESSABLE_ENTITY)

    try:
        n = int(values[0])
    except ValueError:
        return await send_error(send, HTTPStatus.UNPROCESSABLE_ENTITY)

    if n < 0 or n > MAX_FACTORIAL_N:
        return await send_error(send, HTTPStatus.BAD_REQUEST)

    await send_json(send, HTTPStatus.OK, {"result": math.factorial(n)})


async def handle_fibonacci(param: str, send) -> None:
    try:
        n = int(param)
    except ValueError:
        return await send_error(send, HTTPStatus.UNPROCESSABLE_ENTITY)

    if n < 0 or n > MAX_FIBONACCI_N:
        return await send_error(send, HTTPStatus.BAD_REQUEST)

    await send_json(send, HTTPStatus.OK, {"result": fibonacci(n)})


def reject_constant(name: str):
    # json.loads accepts NaN / Infinity by default, but they aren't valid JSON
    raise ValueError(f"invalid constant {name}")


def parse_numbers_from_body(body: bytes) -> list | None:
    try:
        numbers = json.loads(body, parse_constant=reject_constant)
    except ValueError:
        return None

    if not isinstance(numbers, list):
        return None

    # bool is a subclass of int, so it has to be excluded explicitly
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in numbers):
        return None

    return numbers


def parse_numbers_from_query(value: str) -> list | None:
    """Parses "1,2,3" from /mean?numbers=1,2,3"""
    if not value.strip():
        return []

    try:
        return [float(x) for x in value.split(",")]
    except ValueError:
        return None


async def handle_mean(scope, receive, send) -> None:
    body = await read_body(receive)
    if body is None:
        return await send_error(send, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)

    query = parse_qs(scope["query_string"].decode(), keep_blank_values=True)
    if body:
        numbers = parse_numbers_from_body(body)
    elif "numbers" in query:
        numbers = parse_numbers_from_query(query["numbers"][0])
    else:
        numbers = None

    if numbers is None:
        return await send_error(send, HTTPStatus.UNPROCESSABLE_ENTITY)

    # 1e999 parses as inf, so the values themselves have to be checked too
    if not all(isinstance(x, int) or math.isfinite(x) for x in numbers):
        return await send_error(send, HTTPStatus.UNPROCESSABLE_ENTITY)

    if not numbers:
        return await send_error(send, HTTPStatus.BAD_REQUEST)

    try:
        result = sum(numbers) / len(numbers)
        if not math.isfinite(result):
            # e.g. [1e308, 1e308]: the sum overflows, dividing first doesn't
            result = sum(x / len(numbers) for x in numbers)
    except OverflowError:
        return await send_error(send, HTTPStatus.BAD_REQUEST)

    if not math.isfinite(result):
        return await send_error(send, HTTPStatus.BAD_REQUEST)

    await send_json(send, HTTPStatus.OK, {"result": result})


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
        return await handle_lifespan(receive, send)

    if scope["type"] != "http":
        return

    method = scope["method"]
    path = scope["path"]

    if method == "GET" and path == "/factorial":
        return await handle_factorial(scope, send)

    if method == "GET" and path.startswith("/fibonacci/"):
        return await handle_fibonacci(path.removeprefix("/fibonacci/"), send)

    if method == "GET" and path == "/mean":
        return await handle_mean(scope, receive, send)

    await send_error(send, HTTPStatus.NOT_FOUND)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
