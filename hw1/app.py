from typing import Any, Awaitable, Callable
import json
from urllib.parse import parse_qs


async def read_body(receive) -> bytes:
    body = b""
    while True:
        message = await receive()
        if message["type"] == "http.request":
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break
        elif message["type"] == "http.disconnect":
            break
    return body


def fibonacci(n):
    if n <= 1:
        return n
    else:
        a, b = 0, 1
        for _ in range(n-1):
            a, b = b, a + b
        return b


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

    path = scope.get('path', '')
    query_bytes = scope.get('query_string', b'')
    query_string = query_bytes.decode('utf-8')
    params = parse_qs(query_string)
    status = 500
    result = None
    if path[:10] == '/fibonacci':
        if not path.count('/') == 2:
            status = 422
        else:
            try:
                n = int(path.split('/')[2])
                if n < 0:
                    status = 400
                else:
                    status = 200
                    result = fibonacci(n)
            except:
                status = 422
            
    elif path == '/factorial':
        n: str = params.get('n', '-1')[0]
        try:
            n = int(n)
            if n < 0:
                status = 400
            else:
                status = 200
                import math
                result = math.factorial(int(n))
        except:
            status = 422
    elif path == '/mean':
        body = await read_body(receive)
        try:
            data = json.loads(body) if body else None
        except:
            data = None

        if not isinstance(data, list):
            status = 422
        elif len(data) == 0:
            status = 400
        else:
            try:
                result = sum(data) / len(data)
                status = 200
            except TypeError:
                status = 422
    else:
        status = 404

    body_bytes = json.dumps({'result': result}).encode('utf-8')
    await send({
        'type': 'http.response.start',
        'status': status,
        'headers': [
            (b'content-type', b'application/json'),
        ],
    })
    await send({
        'type': 'http.response.body',
        'body': body_bytes,
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
