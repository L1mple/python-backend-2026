from typing import Any, Awaitable, Callable


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
            await send({"type": f"{message['type']}.complete"})

    path = scope["path"].rstrip("/")
    status = 404
    result = None

    if scope["method"] == "GET":
        if path == "/factorial":
            kvs = scope["query_string"].decode()
            n = None
            for kv in kvs.split("&"):
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    if k == "n":
                        n = v
            status, result = compute_number(n, factorial)
        elif path.startswith("/fibonacci/"):
            status, result = compute_number(path.removeprefix("/fibonacci/"), fibonacci)
        elif path == "/mean":
            raw_bytes = await read_bytes(receive)
            status, result = mean(raw_bytes)

    await answer(send, status, result)


def compute_number(raw: str | None, func: Callable[[int], int]) -> tuple[int, int | None]:
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return 422, None
    if n < 0:
        return 400, None
    return 200, func(n)


def factorial(n: int) -> int:
    ans = 1
    for i in range(n):
        ans *= (i + 1)
    return ans


def fibonacci(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def mean(body: bytes) -> tuple[int, float | None]:
    try:
        text = body.decode().strip()
        numbers = [float(item) for item in text[1:-1].split(",") if item.strip()]
    except ValueError:
        return 422, None
    if not numbers:
        return 400, None
    res = sum(numbers) / len(numbers)
    return 200, res


async def read_bytes(receive: Callable[[], Awaitable[dict[str, Any]]]) -> bytes:
    body = b""
    has_more = True
    while has_more:
        message = await receive()
        body += message.get("body", b"")
        has_more = message.get("more_body", False)
    return body


async def answer(send, status, result):
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [[b"content-type", b"application/json"]],
        }
    )
    body = b""
    if status == 200:
        body = f'{{"result": {result}}}'.encode()
    await send({"type": "http.response.body", "body": body})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
