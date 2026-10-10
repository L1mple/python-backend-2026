from typing import Any, Awaitable, Callable
import json


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
    query_string = scope.get("query_string", b"").decode("utf-8")

    async def send_json(status, data):
        body = json.dumps(data).encode("utf-8")
        await send({
            "type": "http.response.start", 
            "status": status,
            "headers": [
                (b"content-type", b"application/json")
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })
        return


    if path == "/factorial":
        if method != "GET":
            await send_json(422, {"error" : "unsupported method"})
            return
        
        if query_string == "":
            await send_json(422, {"error" : "n is requiered"})
            return
        
        key, value = query_string.split("=", 1)
        if key != "n":
            await send_json(422, {"error" : "wrong param"})
            return
        try: 
            n = int(value)
        except ValueError:
            await send_json(422, {"error": "n must be integer"})
            return
        if n < 0:
            await send_json(400, {"error" : "n must be positive"})
            return
        
        res = 1
        for i in range(1, n + 1):
            res *= i
        print("result=", res)
        await send_json(200, {"result" : res})
        return

    if path.startswith("/fibonacci/"):
        if method != "GET":
            await send_json(422, {"error" : "unsupported method"})
            return
        n_string = path[len("/fibonacci/"):]
        try: 
            n = int(n_string)
        except ValueError:
            await send_json(422, {"error": "n must be integer"})
            return
        if n < 0:
            await send_json(400, {"error" : "n must be positive"})
            return
        a, b = 0, 1
        for i in range(n):
            a, b = b, a + b
        await send_json(200, {"result" : b})
        return
        
    if path == "/mean":
        if method != "GET":
            await send_json(422, {"error": "unsupported method"})
            return

        message = await receive()
        body = message.get("body", b"")

        if not body:
            await send_json(422, {"error": "body is required"})
            return

        try:
            nums = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            await send_json(422, {"error": "invalid json"})
            return

        if nums is None:
            await send_json(422, {"error": "numbers are required"})
            return

        if nums == []:
            await send_json(400, {"error": "numbers must not be empty"})
            return

        res = sum(nums) / len(nums)
        await send_json(200, {"result": res})
        return

    await send_json(404, {"error": "not found"})
    return 

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
