from typing import Any, Awaitable, Callable
import json
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
            event = await receive()

            if event["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})

            elif event["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return
    if scope["type"] != "http":
        return

    async def answer(data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                [b"content-type", b"application/json"],
            ]
        })

        await send({
            "type": "http.response.body",
            "body": body,
        })

    method = scope["method"]
    path = scope["path"]

    if method != "GET":
        await answer({"error": "Method Not Found"}, 404)
    elif path == "/factorial":
        params = parse_qs(scope["query_string"].decode("utf-8"), keep_blank_values=True)

        try:
            n = int(params["n"][0])
        except (KeyError, ValueError):
            await answer({"error": "Unprocessable"}, 422)
            return
        if n < 0:
            await answer({"error": "Parameter Error"}, 400)
            return

        def factorial(x):
            ans = 1
            while x > 1:
                ans *= x
                x -= 1
            return ans

        await answer({"result": factorial(n)})

    elif path.startswith("/fibonacci/"):
        raw_n = scope["path"].removeprefix("/fibonacci/")

        try:
            n = int(raw_n)
        except ValueError:
            await answer({"error": "Unprocessable"}, 422)
            return
        if n < 0:
            await answer({"error": "Parameter Error"}, 400)
            return

        def fibonacci(x):
            a, b = 0, 1
            for _ in range(x):
                a, b = b, a + b
            return a

        await answer({"result": fibonacci(n)})
    elif path == "/mean":
        body = bytearray()

        while True:
            event = await receive()

            if event["type"] == "http.disconnect":
                return
            body.extend(event.get("body", b""))

            if not event.get("more_body", False):
                break

        try:
            nums = json.loads(body)
        except json.JSONDecodeError:
            await answer({"error": "Unprocessable"}, 422)
            return

        if not isinstance(nums, list):
            await answer({"error": "Unprocessable"}, 422)
            return

        if not nums:
            await answer({"error": "Parameter Error"}, 400)
            return

        if any(type(x) not in (int, float) for x in nums):
            await answer({"error": "Unprocessable"}, 422)
            return

        await answer({"result": sum(nums) / len(nums)})
    else:
        await answer({"error": "Method Not Found"}, 404)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
