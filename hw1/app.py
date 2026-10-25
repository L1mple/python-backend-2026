from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs
import json

def fibonacci(n: int) -> int:
    if n <= 0:
        return 0
    elif n == 1:
        return 1
    else:
        a, b = 0, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b

def factorial(n: int) -> int:
    if n < 0:
        raise ValueError("Factorial is not defined for negative numbers.")
    elif n == 0 or n == 1:
        return 1
    else:
        result = 1
        for i in range(2, n + 1):
            result *= i
        return result

def mean(numbers: list[float]) -> float:
    if not numbers:
        raise ValueError("Mean is not defined for an empty list.")
    return sum(numbers) / len(numbers)

async def send_response(send: Callable[[dict[str, Any]], Awaitable[None]], status: int, body: Any):
    if status == 200:
        content_type = b"application/json"
        response_body = json.dumps({"result": body}).encode()
    else:
        content_type = b"text/plain"
        response_body = str(body).encode()

    headers = [(b"content-type", content_type)]
    if status == 405:
        headers.append((b"allow", b"GET"))

    await send({
        "type": "http.response.start",
        "status": status,
        "headers": headers,
    })
    await send({"type": "http.response.body", "body": response_body})

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

    method = scope.get("method")
    path = scope.get("path")

    if path not in ("/factorial", "/mean") and not (
        path.startswith("/fibonacci/") and path.count("/") == 2
    ):
        await send_response(send, 404, "Not Found")
        return

    if method != "GET":
        await send_response(send, 405, "Method Not Allowed")
        return

    if path.startswith("/fibonacci/"):
        try:
            n = int(path.rsplit("/", 1)[1])
        except (TypeError, ValueError):
            await send_response(send, 422, "UNPROCESSABLE_ENTITY")
            return
        if n < 0:
            await send_response(send, 400, "Bad Request")
            return
        await send_response(send, 200, fibonacci(n))

    elif path == "/factorial":
        params = parse_qs(scope["query_string"].decode())
        n = params.get("n", [None])[0]

        try:
            n = int(n)
        except (TypeError, ValueError):
            await send_response(send, 422, "UNPROCESSABLE_ENTITY")
            return
        if n < 0:
            await send_response(send, 400, "Bad Request")
            return
        await send_response(send, 200, factorial(n))

    elif path == "/mean":
        body = b""
        while True:
            message = await receive()
            if message["type"] != "http.request":
                return
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break

        try:
            if body:
                numbers = json.loads(body)
            else:
                values = parse_qs(scope["query_string"].decode()).get("numbers")
                if values is None:
                    await send_response(send, 422, "UNPROCESSABLE_ENTITY")
                    return
                numbers = [float(value) for value in values[0].split(",")]
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            await send_response(send, 422, "UNPROCESSABLE_ENTITY")
            return
        if not isinstance(numbers, list) or any(
            isinstance(number, bool) or not isinstance(number, (int, float))
            for number in numbers
        ):
            await send_response(send, 422, "UNPROCESSABLE_ENTITY")
            return
        if not numbers:
            await send_response(send, 400, "Bad Request")
            return
        await send_response(send, 200, mean(numbers))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
