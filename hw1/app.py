
import json
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs

# Псевдонимы типов: чтобы не писать эту простыню в каждой функции.
Scope = dict[str, Any]
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]

MAX_N = 1000
MAX_FIB_N = 10_000


class ApiError(Exception):
    """Ошибка, которую мы осознанно показываем клиенту."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


async def read_body(receive: Receive) -> bytes | None:
    """Собирает тело запроса из событий. None — клиент отключился."""
    body = b""
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            return None
        body += message.get("body", b"")
        if not message.get("more_body", False):
            return body


async def send_json(send: Send, status: int, payload: dict[str, Any]) -> None:
    """Единственное место в файле, которое умеет отвечать клиенту."""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


def query_param(scope: Scope, name: str) -> str:
    """Достаёт один обязательный параметр из query string."""
    params = parse_qs(scope["query_string"].decode("utf-8"), keep_blank_values=True)
    values = params.get(name)
    if not values or not values[-1]:
        raise ApiError(422, f"параметр '{name}' обязателен")
    return values[-1]

def path_param(scope: Scope, prefix: str) -> str:
    path = scope["path"].rstrip("/")
    if not path.startswith(prefix):
        raise ApiError(404, "эндпоинт не найден")
    return path.removeprefix(prefix)

def factorial(n: int) -> int:
    result = 1
    for k in range(2, n+1):
        result*=k
    return result

def fibonacci(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
    
    
def to_int(raw: str, name: str) -> int:
    """Строка → целое, иначе 422."""
    try:
        return int(raw)
    except ValueError:
        raise ApiError(422, f"'{name}' должен быть целым числом") from None


# ─────────────── обработчики ручек ───────────────

async def handle_factorial (scope: Scope, send: Send) -> None:
    n = to_int(query_param(scope, "n"), "n")
    if n < 0:
        raise ApiError(400, "'n' должен быть неотрицательным")
    if n > MAX_N:
        raise ApiError(400, f"'n' не больше {MAX_N}")

    await send_json(send, 200, {"result": factorial(n)})


async def handle_fibonacci  (scope: Scope, send: Send) -> None:
    n = to_int(path_param(scope, "/fibonacci/"), "n")
    if n < 0:
        raise ApiError(400, 'n должен быть неотрицательным')
    if n > MAX_FIB_N:
         raise ApiError(400, f"n не больше {MAX_FIB_N}")
    await send_json(send, 200, {"result": fibonacci(n)})



async def handle_mean(receive: Receive, send: Send) -> None:
    body = await read_body(receive)
    if body is None:
        return  # клиент отвалился, отвечать некому
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise ApiError(422, "тело запроса — не JSON") from None

    if not isinstance(data, list):
        raise ApiError(422, "ожидался JSON-массив чисел")
    if not data:
        raise ApiError(400, "массив пустой — считать нечего")
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in data):
        raise ApiError(422, "все элементы массива должны быть числами")

    await send_json(send, 200, {"result": sum(data) / len(data)})




async def route(scope: Scope, receive: Receive, send: Send) -> None:
    path = scope["path"].rstrip("/") or "/"
    method = scope["method"]

    if method == "GET" and path == "/factorial":
        await handle_factorial(scope, send)
    elif method == "GET" and path.startswith("/fibonacci/"):
        await handle_fibonacci(scope, send)
    elif method == "GET" and path == "/mean":
        await handle_mean(receive, send)
    else:
        raise ApiError(404, "эндпоинт не найден")


async def lifespan(receive: Receive, send: Send) -> None:
    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif message["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return


# ─────────────── точка входа ASGI ───────────────
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
        await lifespan(receive, send)
        return
    if scope["type"] != "http":
        return

    try:
        await route(scope, receive, send)
    except ApiError as error:
        await send_json(send, error.status, {"detail": error.detail})
    except Exception as error:  # последний рубеж: не отдаём клиенту трейсбек
        print("unhandled:", repr(error))
        await send_json(send, 500, {"detail": "внутренняя ошибка"})



if __name__ == "__main__":
    import uvicorn
    #uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
    uvicorn.run("app:application", host="127.0.0.1", port=8001, reload=True)