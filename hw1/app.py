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
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return

    if scope["type"] != "http":
        return

    path = scope["path"]
    method = scope["method"]
    params = parse_qs(scope.get("query_string", b"").decode("utf-8", errors="replace"), keep_blank_values=True)

    if path not in ("/factorial", "/mean", "/fibonacci") and not path.startswith("/fibonacci/"):
        await send_response_json(
            send=send,
            status_code=404,
            body={"error": "Broken address"}
        )
        return

    if method != "GET":
        await send_response_json(
            send=send,
            status_code=422,
            body={"error": "Unsupported method"}
        )
        return

    if path == "/factorial":
        await process_fact(params, send)

    elif path == "/mean":
        await process_mean(params, receive, send)

    else:
        await process_fib(path, send)


async def process_fact(
    params: dict[str, list[str]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    """
    асинхронная функция обработки факториала
    """

    if len(params) != 1 or "n" not in params or len(params["n"]) != 1:
        await send_response_json(
            send=send,
            status_code=422,
            body={"error": "Unsupported params"}
        )
        return

    try:
        n = int(params["n"][0])
    except ValueError:
        await send_response_json(
            send=send,
            status_code=422,
            body={"error": "Unsupported params"}
        )
        return

    if n < 0:
        await send_response_json(
            send=send,
            status_code=400,
            body={"error": "Number must be non-negative"}
        )
        return

    await send_response_json(
        send=send,
        body={"result": math.factorial(n)}
    )


async def process_fib(
    path: str,
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    """
    Асинхронное вычисление числа фибоначчи
    """

    parts = path[1:].split('/')[1:]

    if len(parts) != 1:
        await send_response_json(
            send=send,
            status_code=422,
            body={"error": "Unsupported params"}
        )
        return

    try:
        n = int(parts[0])
    except ValueError:
        await send_response_json(
            send=send,
            status_code=422,
            body={"error": "Unsupported params"}
        )
        return

    if n < 0:
        await send_response_json(
            send=send,
            status_code=400,
            body={"error": "Number must be non-negative"}
        )
        return

    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b

    await send_response_json(
        send=send,
        body={"result": a}
    )


async def process_mean(
    params: dict[str, list[str]],
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    """
    Асинхронное вычисление среднего арифметического
    """

    body = bytearray()
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            return
        body.extend(message.get("body", b""))
        if not message.get("more_body", False):
            break

    try:
        if params:
            if len(params) != 1 or "numbers" not in params or len(params["numbers"]) != 1 or body:
                raise ValueError
            numbers = [float(number) for number in params["numbers"][0].split(',')]
        else:
            numbers = json.loads(body)

        if not isinstance(numbers, list):
            raise ValueError
        if any(type(number) not in (int, float) or not math.isfinite(number) for number in numbers):
            raise ValueError
    except (ValueError, UnicodeDecodeError, OverflowError):
        await send_response_json(
            send=send,
            status_code=422,
            body={"error": "Unsupported params"}
        )
        return

    if not numbers:
        await send_response_json(
            send=send,
            status_code=400,
            body={"error": "Numbers must not be empty"}
        )
        return

    result = math.fsum(number / len(numbers) for number in numbers)
    await send_response_json(
        send=send,
        body={"result": result}
    )


async def send_response_json(
    send: Callable[[dict[str, Any]], Awaitable[None]],
    status_code: int = 200,
    body: dict[str, Any] | None = None,
) -> None:
    """
    Асинхронная отправка ответа с json телом
    """

    await send({
        "type": "http.response.start",
        "status": status_code,
        "headers": [
            [b"content-type", b"application/json"]
        ]
    })

    await send({
        "type": "http.response.body",
        "body": json.dumps(body if body is not None else {}).encode()
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
