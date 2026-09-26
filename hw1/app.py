import json
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs


async def application(
    scope: dict[str, Any],
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
):
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

     method = scope["method"]
     path = scope["path"]

     async def response(status: int, result: Any = None) -> None:
         body = b""

         if result is not None:
             body = json.dumps({"result": result}).encode("utf-8")

         await send(
             {
                 "type": "http.response.start",
                 "status": status,
                 "headers": [(b"content-type", b"application/json")],
             }
         )
         await send(
             {
                 "type": "http.response.body",
                 "body": body,
             }
         )

     if method == "GET" and path == "/factorial":
         query = parse_qs(
             scope.get("query_string", b"").decode(),
             keep_blank_values=True,
         )

         if "n" not in query or len(query["n"]) != 1:
             await response(422)
             return

         try:
             n = int(query["n"][0])
         except ValueError:
             await response(422)
             return

         if n < 0:
             await response(400)
             return

         result = 1
         for number in range(2, n + 1):
             result *= number

         await response(200, result)
         return

     if method == "GET" and path.startswith("/fibonacci/"):
         value = path.removeprefix("/fibonacci/")

         try:
             n = int(value)
         except ValueError:
             await response(422)
             return

         if n < 0:
             await response(400)
             return

         first = 0
         second = 1

         for _ in range(n):
             first, second = second, first + second

         await response(200, first)
         return

     if method == "GET" and path == "/mean":
         body = b""

         while True:
             message = await receive()

             if message["type"] != "http.request":
                 continue

             body += message.get("body", b"")

             if not message.get("more_body", False):
                 break

         if not body:
             await response(422)
             return

         try:
             numbers = json.loads(body)
         except (json.JSONDecodeError, UnicodeDecodeError):
             await response(422)
             return

         if not isinstance(numbers, list):
             await response(422)
             return

         if not numbers:
             await response(400)
             return

         if any(
             not isinstance(number, (int, float)) or isinstance(number, bool)
             for number in numbers
         ):
             await response(422)
             return

         await response(200, sum(numbers) / len(numbers))
         return

     await response(404)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
