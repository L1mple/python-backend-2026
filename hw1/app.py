from typing import Any, Awaitable, Callable
from math import factorial
from urllib.parse import parse_qs
import logging
import json
import http


logger = logging.getLogger(__name__)

Sender = Callable[[dict[str, Any]], Awaitable[None]]

async def application(
    scope: dict[str, Any],
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Sender,
):
    """
    Args:
        scope: Словарь с информацией о запросе
        receive: Корутина для получения сообщений от клиента
        send: Корутина для отправки сообщений клиенту
    """
    logger.info(f"scope: {scope}")

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
                break
        return  

    if scope["type"] != "http":
        return

    message = await receive()
    logger.info(f"MSG: {message}")

    
    method = scope["method"]
    path: str = scope["path"]
    query = parse_qs(scope["query_string"].decode("ascii"))
    logger.info("All: %s %s %s", method, path, query)

    if method == "GET" and path == "/factorial":
        await handle_factorial(send, method, path, query)
    elif method == "GET" and path.startswith("/fib"):
        await handle_fib(send, method, path, query)
    elif method == "GET" and path == "/mean":
        await handle_mean(send, method, path, query, message["body"])
    else:
        await send_error(send, http.HTTPStatus.NOT_FOUND)


async def handle_factorial(send: Sender, method: str, path: str, query: str):
    try:
        n = int(query["n"][0])
    except:
        await send_error(send, http.HTTPStatus.UNPROCESSABLE_ENTITY)
        return
    
    if n < 0:
        await send_error(send, http.HTTPStatus.BAD_REQUEST)
        return
    
    await send_message(send, {"result": factorial(n)})


async def handle_fib(send: Sender, method: str, path: str, query: str):
    try:
        logger.info(f"AAAA {path.split('/')[2]}")
        n = int(path.split('/')[2]) 
        logger.info(f"N: {n}")
    except:
        await send_error(send, http.HTTPStatus.UNPROCESSABLE_ENTITY)
        return

    if n < 0:
        await send_error(send, http.HTTPStatus.BAD_REQUEST)
        return

    await send_message(send, {"result": fib(n)})


async def handle_mean(send: Sender, method: str, path: str, query: str, body: str):
    try:
        args = list(json.loads(body))
    except:
        await send_error(send, http.HTTPStatus.UNPROCESSABLE_ENTITY)
        return

    if len(args) == 0:
        await send_error(send, http.HTTPStatus.BAD_REQUEST)
        return

    await send_message(send, {"result": sum(args) / len(args)})


async def send_message(send: Sender, dict: dict[str, Any]):
    await send({
        "type": "http.response.start",
        "status": http.HTTPStatus.OK,
        "headers": [
            [b"content-type", b"application/json"]
        ],
    })
    await send({
        "type": "http.response.body",
        "body": bytes(json.dumps(dict), 'utf-8')
    })


async def send_error(send: Sender, err: http.HTTPStatus, err_msg: str = ""):
    await send({
        "type": "http.response.start",
        "status": err,
         "headers": [
            [b"content-type", b"application/json"]
        ],
    })
    await send({
        "type": "http.response.body",
        "body": bytes(err_msg, 'utf-8')
    })

def fib(n):
    if n == 0:
        return 0
    if n == 1:
        return 1
    return fib(n - 1) + fib(n - 2)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
