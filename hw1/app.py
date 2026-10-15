import json
import math
import re
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs


async def application(
    scope: dict[str, Any],
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    # Служебные события запуска и остановки приложения.
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

    async def send_json(status: int, data: dict[str, Any]) -> None:
        body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json")],
        })
        await send({"type": "http.response.body", "body": body})

    def parse_integer(value: str) -> int:
        value = value.strip()
        if re.fullmatch(r"[+-]?[0-9]+", value) is None:
            raise ValueError("Expected an integer")
        return int(value)

    path = scope["path"]
    if scope["method"] != "GET":
        await send_json(404, {"detail": "Not found"})
        return

    if path == "/factorial":
        try:
            query = parse_qs(
                scope.get("query_string", b"").decode("utf-8"),
                keep_blank_values=True,
            )
            n = parse_integer(query.get("n", [""])[-1])
        except (ValueError, UnicodeError):
            await send_json(422, {"detail": "n must be an integer"})
            return

        if n < 0:
            await send_json(400, {"detail": "n must be non-negative"})
            return

        await send_json(200, {"result": math.factorial(n)})
        return

    if path.startswith("/fibonacci/"):
        parameter = path[len("/fibonacci/"):]
        if "/" in parameter:
            await send_json(404, {"detail": "Not found"})
            return

        try:
            n = parse_integer(parameter)
        except ValueError:
            await send_json(422, {"detail": "n must be an integer"})
            return

        if n < 0:
            await send_json(400, {"detail": "n must be non-negative"})
            return

        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b

        # Повторяем код лекции: b здесь равно F(n + 1).
        await send_json(200, {"result": b})
        return

    if path == "/mean":
        chunks = []
        while True:
            event = await receive()
            if event["type"] == "http.disconnect":
                return
            if event["type"] != "http.request":
                continue
            chunks.append(event.get("body", b""))
            if not event.get("more_body", False):
                break

        try:
            data = json.loads(b"".join(chunks).decode("utf-8"))
            if not isinstance(data, list):
                raise ValueError("Expected a JSON array")
            numbers = [float(item) for item in data]
            if not all(math.isfinite(item) for item in numbers):
                raise ValueError("Expected finite numbers")
        except (ValueError, TypeError, UnicodeError, OverflowError):
            await send_json(422, {"detail": "Body must be a JSON array of numbers"})
            return

        if not numbers:
            await send_json(400, {"detail": "Array must not be empty"})
            return

        result = sum(numbers) / len(numbers)
        if not math.isfinite(result):
            await send_json(400, {"detail": "Mean is outside the supported range"})
            return
        await send_json(200, {"result": result})
        return

    await send_json(404, {"detail": "Not found"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
