import math
from http import HTTPStatus
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs


async def send_json(send, status: HTTPStatus, body: str) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body.encode()})


async def parse_n(send, row: str | None) -> int | None:
    try:
        n = int(row)
    except (TypeError, ValueError):
        await send_json(
            send, HTTPStatus.UNPROCESSABLE_ENTITY, '{"error": "invalid parameter n"}'
        )
        return
    if n < 0:
        await send_json(
            send, HTTPStatus.BAD_REQUEST, '{"error": "n must be non-negative"}'
        )
        return
    return n


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
            event = await receive()
            if event["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif event["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return

    if scope["path"] == "/factorial":
        query = parse_qs(scope["query_string"].decode())
        value = query.get("n")
        n = await parse_n(send, value[0] if value else None)
        if n is None:
            return
        await send_json(send, HTTPStatus.OK, f'{{"result": {math.factorial(n)}}}')
    elif scope["path"].startswith("/fibonacci/"):
        n = await parse_n(send, scope["path"].removeprefix("/fibonacci/"))
        if n is None:
            return
        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b
        await send_json(send, HTTPStatus.OK, f'{{"result": {a}}}')
    elif scope["path"] == "/mean":
        query = parse_qs(scope["query_string"].decode(), keep_blank_values=True)
        value = query.get("numbers")
        if value is None:
            await send_json(
                send,
                HTTPStatus.UNPROCESSABLE_ENTITY,
                '{"error": "missing parameter numbers"}',
            )
            return
        if value[0] == "":
            await send_json(
                send, HTTPStatus.BAD_REQUEST, '{"error": "numbers must not be empty"}'
            )
            return
        try:
            numbers = [float(x) for x in value[0].split(",")]
        except ValueError:
            await send_json(
                send,
                HTTPStatus.UNPROCESSABLE_ENTITY,
                '{"error": "invalid parameter numbers"}',
            )
            return
        await send_json(
            send, HTTPStatus.OK, f'{{"result": {sum(numbers) / len(numbers)}}}'
        )
    else:
        await send_json(send, HTTPStatus.NOT_FOUND, '{"error": "not found"}')


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
