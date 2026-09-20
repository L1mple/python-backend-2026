from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs
import json

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
                    "type": "lifespan.startup.complete",
                })

            elif message["type"] == "lifespan.shutdown":
                await send({
                    "type": "lifespan.shutdown.complete",
                })
                return

    if scope["type"] != "http":
        return

    async def send_response(status: int, body: bytes, content_type: bytes = b"text/plain"):
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", content_type)],
        })

        await send({
            "type": "http.response.body",
            "body": body,
        })

    if scope["method"] == "GET" and scope["path"] == "/factorial":
        query_string = scope["query_string"].decode()
        query = parse_qs(query_string)

        if "n" not in query:
            await send_response(422, b"Unprocessable Entity")
            return

        try:
            n = int(query["n"][0])
        except ValueError:
            await send_response(422, b"Unprocessable Entity")
            return

        if n < 0:
            await send_response(400, b"Bad Request")
            return
        
        result = 1
        for i in range(2, n + 1):
            result *= i

        body = json.dumps({"result": result}).encode()

        await send_response(200, body, b"application/json")
        return

    if scope["method"] == "GET" and scope["path"].startswith("/fibonacci/"):
        value = scope["path"].split("/")[-1]

        try:
            n = int(value)
        except ValueError:
            await send_response(422, b"Unprocessable Entity")
            return

        if n < 0:
            await send_response(400, b"Bad Request")
            return

        if n == 0:
            result = 0
        elif n == 1:
            result = 1
        else:
            a = 0
            b = 1

            for _ in range(2, n + 1):
                a,b = b, a + b

            result = b

        body = json.dumps({"result": result}).encode()

        await send_response(200, body, b"application/json")
        return

    if scope["method"] == "GET" and scope["path"] == "/mean":
        message = await receive()
        body = message.get("body",b"")

        if not body:
            await send_response(422, b"Unprocessable Entity")
            return

        try:
            numbers = json.loads(body)
        except json.JSONDecodeError:
            await send_response(422, b"Unprocessable Entity")
            return

        if numbers is None:
            await send_response(422, b"Unprocessable Entity")
            return

        if not isinstance(numbers, list):
            await send_response(400, b"Bad Request")
            return

        if len(numbers) == 0:
            await send_response(400, b"Bad Request")
            return

        if not all(isinstance(number, (int, float)) for number in numbers):
            await send_response(400, b"Bad Request")
            return

        result = sum(numbers) / len(numbers)

        response_body = json.dumps({"result": result}).encode()

        await send_response(200, response_body, b"application/json")
        return

    
    await send_response(404, b"Not Found")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:application",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )

