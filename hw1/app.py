import json
import math
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs


async def _handle_lifespan(
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    """Подтверждает запуск и остановку приложения."""
    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif message["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return


def _parse_n(value: str) -> tuple[int, int | None]:
    """Разбирает неотрицательное целое число."""
    try:
        n = int(value)
    except ValueError:
        return 422, None
    if n < 0:
        return 400, None
    return 200, n


def _fibonacci(n: int) -> int:
    """Вычисляет число Фибоначчи с номером n."""
    first, second = 0, 1
    for _ in range(n):
        first, second = second, first + second
    return first


async def _mean(
    query_string: bytes,
    receive: Callable[[], Awaitable[dict[str, Any]]],
) -> tuple[int, float | None]:
    """Читает список чисел и вычисляет среднее."""
    query = parse_qs(query_string.decode(), keep_blank_values=True)
    if "numbers" in query:
        value = query["numbers"][0]
        if not value:
            return 400, None
        try:
            numbers: object = [float(item) for item in value.split(",")]
        except ValueError:
            return 422, None
    else:
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break
        try:
            numbers = json.loads(body) if body else None
        except (ValueError, UnicodeDecodeError):
            return 422, None

    if not isinstance(numbers, list):
        return 422, None
    if not numbers:
        return 400, None
    if any(
        type(number) not in (int, float)
        or (isinstance(number, float) and not math.isfinite(number))
        for number in numbers
    ):
        return 422, None
    return 200, sum(numbers) / len(numbers)


async def _send_response(
    send: Callable[[dict[str, Any]], Awaitable[None]],
    status: int,
    result: int | float | None,
) -> None:
    """Отправляет JSON-ответ по протоколу ASGI."""
    body = json.dumps({"result": result} if status == 200 else {}).encode()
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [(b"content-type", b"application/json")],
    })
    await send({"type": "http.response.body", "body": body})


async def application(
    scope: dict[str, Any],
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
):
    """Обрабатывает HTTP-запросы математического API."""
    if scope["type"] == "lifespan":
        await _handle_lifespan(receive, send)
        return

    path = scope["path"]
    status = 200
    result: int | float | None = None

    known_paths = ("/factorial", "/mean", "/fibonacci")
    if path not in known_paths and not path.startswith("/fibonacci/"):
        status = 404
    elif scope["method"] != "GET":
        status = 422
    elif path == "/factorial":
        query = parse_qs(
            scope["query_string"].decode(), keep_blank_values=True
        )
        status, n = _parse_n(query.get("n", [""])[0])
        if n is not None:
            result = math.factorial(n)
    elif path == "/mean":
        status, result = await _mean(scope["query_string"], receive)
    else:
        value = path.removeprefix("/fibonacci/")
        status, n = _parse_n(value)
        if n is not None:
            result = _fibonacci(n)

    await _send_response(send, status, result)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
