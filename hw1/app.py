import json
from typing import Any, Awaitable, Callable


def factorial(n: int) -> int:
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return 1
    
    result = 1
    for i in range(1, n + 1):
        result *= i
    return result


def fibonacci(n: int) -> int:
    if n < 0:
        raise ValueError("n must be non-negative")
    
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def mean(numbers: list[float]) -> float:
    if not numbers:
        raise ValueError("numbers must not be empty")
    return sum(numbers) / len(numbers)


async def application(
    scope: dict[str, Any],
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
):
    if scope["type"] == "lifespan":
        while True:
            message = await receive()

            if message["type"] == "lifespan.startup":
                await send({
                    "type": "lifespan.startup.complete"
                })
            elif message["type"] == "lifespan.shutdown":
                await send({
                    "type": "lifespan.shutdown.complete"
                })
                return

    if scope["type"] != "http":
        return

    method = scope["method"]
    path = scope["path"]

    if method == "GET" and path == "/factorial":
        query = scope["query_string"].decode()
        number = query.split("=")[-1] if "=" in query else None
        if number is None:
            status_code = 422
            response_body = {"error": "Missing 'n' parameter"}
        else:
            try:
                n = int(number)
                result = factorial(n)
                status_code = 200
                response_body = {"result": result}
            except ValueError as e:
                if str(e) == "n must be non-negative":
                    status_code = 400
                else:
                    status_code = 422
                response_body = {"error": str(e)}

    elif method == "GET" and path.startswith("/fibonacci/"):
        number = path.split("/")[-1]
        try:
            n = int(number)
            result = fibonacci(n)
            status_code = 200
            response_body = {"result": result}
        except ValueError as e:
            if str(e) == "n must be non-negative":
                status_code = 400
            else:
                status_code = 422
            response_body = {"error": str(e)}

    elif method == "GET" and path == "/mean":
        try:
            message = await receive()
            data = json.loads(message["body"])
            if data is None:
                status_code = 422
                response_body = {"error": "Invalid JSON"}
            else:
                result = mean(data)
                status_code = 200
                response_body = {"result": result}
        except ValueError as e:
            status_code = 400
            response_body = {"error": str(e)}
        except (TypeError, json.JSONDecodeError):
            status_code = 422
            response_body = {"error": "Invalid JSON"}

    else:
            status_code = 404
            response_body = {"error": "Not Found"}


    await send({
        "type": "http.response.start",
        "status": status_code,
        "headers": [
            (b"content-type", b"application/json"),
        ],
    })

    await send({
        "type": "http.response.body",
        "body": json.dumps(response_body).encode(),
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)