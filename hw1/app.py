import json

from typing import Any, Awaitable, Callable



def factorial(n: int) -> int:
    if n == 1:
        return 1
    if n < 1:
        return 1
    result = n * factorial(n-1)
    return result

def fibonacci(n: int) -> int:
    if n == 0:
        return 0
    if n == 1:
        return 1
    return fibonacci(n - 1) + fibonacci(n - 2)


def mean(n:list[float]) -> float:
    my_sym = 0
    for i in n:
        my_sym += i
    res = my_sym / len(n)
    return res


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

    if scope["type"] == "http" and scope["path"].startswith("/factorial"):
        query = scope["query_string"].decode("utf-8")

        try:
            key, value = query.split("=")
            var = int(value)
        except (ValueError, IndexError):
            await send({"type": "http.response.start", "status": 422,"headers": []})
            await send({"type": "http.response.body", "body": b""})
            return

        if var < 0:
            await send({"type": "http.response.start", "status": 400,"headers": []})
            await send({"type": "http.response.body", "body": b""})
            return
        result = factorial(var)

        await send({"type": "http.response.start", "status": 200,"headers": []})
        await send({"type": "http.response.body", "body": json.dumps({"result": result}).encode("utf-8")})

    elif scope["type"] == "http" and scope["path"].startswith("/fibonacci/"):

        try:
            path = scope["path"]
            vars = path.split("/")
            var = int(vars[2])
        except (ValueError, IndexError):
            await send({"type": "http.response.start", "status": 422,"headers": []})
            await send({"type": "http.response.body", "body": b""})
            return
        if var < 0:
            await send({"type": "http.response.start", "status": 400,"headers": []})
            await send({"type": "http.response.body", "body": b""})
            return
        result = fibonacci(var)

        await send({"type": "http.response.start", "status": 200,"headers": []})
        await send({"type": "http.response.body", "body": json.dumps({"result": result}).encode("utf-8")})

    elif scope["type"] == "http" and scope["path"] == "/mean":

        message = await receive()
        body = message["body"]

        if not body:
            await send({"type": "http.response.start", "status": 422,"headers": []})
            await send({"type": "http.response.body", "body": b""})
            return
        value = json.loads(body)

        if value is None:
            await send({"type": "http.response.start", "status": 422, "headers": []})
            await send({"type": "http.response.body", "body": b""})
            return

        if len(value) == 0:
            await send({"type": "http.response.start", "status": 400,"headers": []})
            await send({"type": "http.response.body", "body": b""})
            return

        result = mean(value)

        await send({"type": "http.response.start", "status": 200,"headers": []})
        await send({"type": "http.response.body", "body": json.dumps({"result": result}).encode("utf-8")})
    else:
        await send({"type": "http.response.start", "status": 404,"headers": []})
        await send({"type": "http.response.body","body": b""})

    #await send({"type": "http.response.start", "status": 200})
    #await send({"type": "http.response.body", "body": b"Hello, world"})



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
