import json
import math
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs


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
    # TODO: Ваша реализация здесь

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

    async def respond(status: int, data: dict[str, Any]):
        response_body = json.dumps(
            data,
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")

        headers = [(b"content-type", b"application/json; charset=utf-8")]
        if status == 405:
            headers.append((b"allow", b"GET"))

        await send({
            "type": "http.response.start",
            "status": status,
            "headers": headers,
        })
        await send({
            "type": "http.response.body",
            "body": response_body,
        })

    path = scope["path"]
    parts = path.strip("/").split("/")
    is_fibonacci = (
            len(parts) == 2
            and parts[0] == "fibonacci"
            and path == f"/fibonacci/{parts[1]}"
    )

    if path not in ("/factorial", "/mean") and not is_fibonacci:
        await respond(404, {"detail": "Endpoint not found"})
        return

    if scope["method"] != "GET":
        await respond(405, {"detail": "Only GET is supported"})
        return

    if path == "/factorial" or is_fibonacci:
        try:
            if path == "/factorial":
                query = parse_qs(
                    scope.get("query_string", b"").decode("utf-8"),
                    keep_blank_values=True,
                )
                raw_n = query["n"][-1]
            else:
                raw_n = parts[1]
            n = int(raw_n)
        except (KeyError, ValueError):
            await respond(422, {"detail": "n must be an integer"})
            return

        if n < 0:
            await respond(400, {"detail": "n must be non-negative"})
            return

        if path == "/factorial":
            result = math.factorial(n)
        else:
            a, b = 0, 1
            for _ in range(n):
                a, b = b, a + b
            result = b

        await respond(200, {"result": result})
        return

    body = bytearray()
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            return
        body.extend(message.get("body", b""))
        if not message.get("more_body", False):
            break

    try:
        numbers = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        await respond(422, {"detail": "Body must be a JSON array of numbers"})
        return

    if not isinstance(numbers, list):
        await respond(422, {"detail": "Body must be a JSON array of numbers"})
        return

    if not numbers:
        await respond(400, {"detail": "Array must not be empty"})
        return

    if any(type(number) not in (int, float) for number in numbers):
        await respond(422, {"detail": "Every item must be a number"})
        return

    try:
        if not all(math.isfinite(number) for number in numbers):
            raise ValueError
        result = sum(numbers) / len(numbers)
        if not math.isfinite(result):
            raise ValueError
    except (ValueError, OverflowError):
        await respond(422, {"detail": "Numbers and result must be finite"})
        return

    await respond(200, {"result": result})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
