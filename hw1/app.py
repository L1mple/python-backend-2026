from typing import Any, Awaitable, Callable
import json
import math
from http import HTTPStatus
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
    async def response(status, data):
        body = json.dumps(data).encode()
        await send({'type': 'http.response.start', 'status': status, "headers": [(b"content-type", b"application/json")]})
        await send({'type': 'http.response.body', 'body': body})

    method = scope.get('method', '')
    path = scope.get('path', '')

    # 1. GET /factorial
    if method == 'GET' and path == '/factorial':
        q = parse_qs(scope.get('query_string', b"").decode())
        if set(q.keys()) != {'n'}:
            return await response(422, {})
        try:
            n = int(q['n'][0])
        except ValueError: 
            return await response(422, {})
        if n < 0:
            return await response(400, {})
        return await response(200, {'result': math.factorial(n)})


    # 2. GET /fibonacci
    if method == 'GET' and path.startswith('/fibonacci/'):
        try:
            n = int(path[len('/fibonacci/'):])
        except ValueError:
            return await response(422, {})
        if n < 0:
            return await response(400, {})
        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b
        return await response(200, {'result': a})


    # 3. GET /mean
    if method == 'GET' and path == '/mean':
        body = b""
        while True:
            msg = await receive()
            body += msg.get('body', b"")
            if not msg.get('more_body', False):
                break
        if not body:
            return await response(422, {})
        data = json.loads(body)
        if data is None or not isinstance(data, list):
            return await response(422, {})
        if not data:
            return await response(400, {})
        return await response(200, {'result': sum(data) / len(data)})

    return await response(404, {})
    

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
