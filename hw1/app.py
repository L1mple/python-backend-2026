import json
from http import HTTPStatus
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
    if scope["type"] == "lifespan":
        await lifespan(receive, send)
        return
    if scope["type"] != "http":
        return

    method = scope["method"]
    path = scope["path"]

    if method != "GET":
        await reply(send, HTTPStatus.NOT_FOUND, None)
        return

    if path == "/factorial":
        await factorial(scope, send)
        return
    if path == "/mean":
        await mean(receive, send)
        return
    if path.startswith("/fibonacci/"):
        await fibonacci(path, send)
        return

    await reply(send, HTTPStatus.NOT_FOUND, None)


async def lifespan(receive, send):
    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif message["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return


async def reply(send, status, payload):
    body = b""
    headers = []
    if payload is not None:
        body = json.dumps(payload).encode()
        headers = [[b"content-type", b"application/json"]]
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": headers,
    })
    await send({"type": "http.response.body", "body": body})


def as_int(raw):
    if raw is None or raw == "":
        return None
    if len(raw) > 1 and raw[0] == "0":
        return None
    sign = raw
    if sign[0] == "-":
        sign = sign[1:]
        if sign == "" or (len(sign) > 1 and sign[0] == "0"):
            return None
    if not sign.isdigit():
        return None
    return int(raw)


async def factorial(scope, send):
    params = parse_qs(scope.get("query_string", b"").decode(), keep_blank_values=True)
    if "n" not in params or len(params["n"]) != 1:
        await reply(send, HTTPStatus.UNPROCESSABLE_ENTITY, None)
        return
    n = as_int(params["n"][0])
    if n is None:
        await reply(send, HTTPStatus.UNPROCESSABLE_ENTITY, None)
        return
    if n < 0:
        await reply(send, HTTPStatus.BAD_REQUEST, None)
        return

    acc = 1
    for i in range(2, n + 1):
        acc *= i
    await reply(send, HTTPStatus.OK, {"result": acc})


async def fibonacci(path, send):
    tail = path[len("/fibonacci/"):]
    if "/" in tail:
        await reply(send, HTTPStatus.NOT_FOUND, None)
        return
    n = as_int(tail)
    if n is None:
        await reply(send, HTTPStatus.UNPROCESSABLE_ENTITY, None)
        return
    if n < 0:
        await reply(send, HTTPStatus.BAD_REQUEST, None)
        return

    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    await reply(send, HTTPStatus.OK, {"result": a})


async def read_body(receive):
    chunks = []
    more = True
    while more:
        message = await receive()
        if message["type"] != "http.request":
            break
        chunks.append(message.get("body", b""))
        more = message.get("more_body", False)
    return b"".join(chunks)


async def mean(receive, send):
    raw = await read_body(receive)
    if not raw:
        await reply(send, HTTPStatus.UNPROCESSABLE_ENTITY, None)
        return
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        await reply(send, HTTPStatus.UNPROCESSABLE_ENTITY, None)
        return
    if not isinstance(data, list):
        await reply(send, HTTPStatus.UNPROCESSABLE_ENTITY, None)
        return
    if len(data) == 0:
        await reply(send, HTTPStatus.BAD_REQUEST, None)
        return

    total = 0
    for x in data:
        if isinstance(x, bool) or not isinstance(x, (int, float)):
            await reply(send, HTTPStatus.UNPROCESSABLE_ENTITY, None)
            return
        total += x
    await reply(send, HTTPStatus.OK, {"result": total / len(data)})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
