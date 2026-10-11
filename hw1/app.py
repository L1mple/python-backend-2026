import json
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
    if (scope["type"] == "lifespan"):
        while True:
            s = await receive()
            if s["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            if s["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return
    elif (scope["type"] == "http"):
        path = scope["path"].split("/")[1:]
        result = -1
        status = 404
        if scope["method"] != "GET":
            pass
        elif path[0] == "factorial" and len(path) == 1:
            query = parse_qs(scope["query_string"].decode("utf-8"), keep_blank_values=True)
            try:
                if set(query) != {"n"} or len(query["n"]) != 1:
                    raise ValueError
                arg = int(query["n"][0])
            except ValueError:
                status = 422
            else:
                if arg < 0:
                    status = 400
                else:
                    result = 1
                    for i in range(arg):
                        result *= i + 1
                    status = 200
        elif path[0] == "fibonacci" and len(path) == 2:
            try:
                arg = int(path[1])
            except ValueError:
                status = 422
            else:
                if arg < 0:
                    status = 400
                else:
                    result = 0
                    next_result = 1
                    for _ in range(arg):
                        result, next_result = next_result, result + next_result
                    status = 200
        elif path[0] == "mean" and len(path) == 1:
            body = b""
            while True:
                s = await receive()
                if s["type"] != "http.request":
                    status = 422
                    break
                body += s.get("body", b"")
                if not s.get("more_body", False):
                    try:
                        numbers = json.loads(body)
                    except (json.JSONDecodeError):
                        status = 422
                    else:
                        if not isinstance(numbers, list):
                            status = 422
                        elif not numbers:
                            status = 400
                        elif any(not isinstance(number, (int, float)) for number in numbers):
                            status = 422
                        else:
                            result = sum(numbers) / len(numbers)
                            status = 200
                    break
        response_body = b""
        headers = []
        if status == 200:
            response_body = json.dumps({"result": result}).encode("utf-8")
            headers = [(b"content-type", b"application/json")]
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": response_body})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
