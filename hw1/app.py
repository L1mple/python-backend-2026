from typing import Any, Awaitable, Callable
import json
import math
from http import HTTPStatus
from urllib.parse import parse_qs

def factorial(n: int) -> int:
    return math.factorial(n)

def fibonacci(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b 
    return a

def mean(nums: list[float | int]) -> float:
    if len(nums) == 0: 
        raise TypeError()
    return sum(nums) / len(nums)

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
    # assert scope["type"] == "http"

    path_segments = [seg for seg in scope.get("path", "").split("/") if seg]
    
    status = HTTPStatus.OK
    response_data = {}

    match path_segments:
        case ["factorial"]:
            query_raw = scope.get("query_string", b"").decode("utf-8")
            query_params = parse_qs(query_raw)
            
            if "n" in query_params and (n_val := query_params["n"]):
                try:
                    n = int(n_val[0])
                    if n < 0:
                        status = HTTPStatus.BAD_REQUEST
                    else:
                        response_data = {"result": factorial(n)}
                except ValueError:
                    status = HTTPStatus.UNPROCESSABLE_ENTITY
            else:
                status = HTTPStatus.UNPROCESSABLE_ENTITY

        case ["fibonacci", n_str]:
            try:
                n = int(n_str)
                if n < 0:
                    status = HTTPStatus.BAD_REQUEST
                else:
                    response_data = {"result": fibonacci(n)}
            except ValueError:
                status = HTTPStatus.UNPROCESSABLE_ENTITY

        case ["fibonacci"]:
            status = HTTPStatus.UNPROCESSABLE_ENTITY

        case ["mean"]:
            body = b""
            received_any = False

            while True:
                message = await receive()
                print("MSG:", message)
                if message["type"] == "http.request":
                    received_any = True
                    body += message.get("body", b"")
                    if not message.get("more_body", False):
                        break
                elif message["type"] == "http.disconnect":
                    break

            if not received_any or body.strip() == b'null':
                # тело не передано → 422
                status = HTTPStatus.UNPROCESSABLE_ENTITY
                response_data = {"result": None}
            else:
                try:
                    numbers = json.loads(body)
                    if not isinstance(numbers, list):
                        raise ValueError
                    result = mean(numbers)
                    response_data = {"result": result}
                except (ValueError, json.JSONDecodeError, TypeError):
                    # тело есть, но некорректно → 400
                    status = HTTPStatus.BAD_REQUEST
                    response_data = {"result": []}

        case _:
            status = HTTPStatus.NOT_FOUND

    response_body = json.dumps(response_data).encode("utf-8")
    
    await send({
        "type": "http.response.start",
        "status": status.value,
        "headers": [(b"content-type", b"application/json")],
    })
    await send({
        "type": "http.response.body",
        "body": response_body,
    })
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
