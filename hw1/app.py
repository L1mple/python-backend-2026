import json
import math
from typing import Any, Awaitable, Callable
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
    if scope['type'] == 'lifespan':
        while True:
            message = await receive()
            if message['type'] == 'lifespan.startup':
                await send({'type': 'lifespan.startup.complete'})
            elif message['type'] == 'lifespan.shutdown':
                await send({'type': 'lifespan.shutdown.complete'})
                return

    method = scope['method']
    path = scope['path']

    if method == 'GET' and path == '/factorial':
        query = parse_qs(scope['query_string'].decode())
        if 'n' not in query:
            await send_response(send, 422, {'error': 'n is required'})
            return
        try:
            n = int(query['n'][0])
        except ValueError:
            await send_response(send, 422, {'error': 'n must be int'})
            return
        if n < 0:
            await send_response(send, 400, {'error': 'n must be >= 0'})
            return
        await send_response(send, 200, {'result': math.factorial(n)})
        return

    if method == 'GET' and path.startswith('/fibonacci/'):
        n_str = path[len('/fibonacci/'):]
        try:
            n = int(n_str)
        except ValueError:
            await send_response(send, 422, {'error': 'n must be int'})
            return
        if n < 0:
            await send_response(send, 400, {'error': 'n must be >= 0'})
            return
        if n == 0:
            result = 0
        elif n == 1:
            result = 1
        else:
            a, b = 0, 1
            for _ in range(2, n + 1):
                a, b = b, a + b
            result = b
        await send_response(send, 200, {'result': result})
        return

    if method == 'GET' and path == '/mean':
        body = b''
        while True:
            message = await receive()
            body += message.get('body', b'')
            if not message.get('more_body', False):
                break
        if not body:
            await send_response(send, 422, {'error': 'body required'})
            return
        try:
            numbers = json.loads(body)
        except json.JSONDecodeError:
            await send_response(send, 422, {'error': 'invalid json'})
            return
        if not isinstance(numbers, list):
            await send_response(send, 422, {'error': 'body must be a list'})
            return
        if len(numbers) == 0:
            await send_response(send, 400, {'error': 'list is empty'})
            return
        mean = sum(numbers) / len(numbers)
        await send_response(send, 200, {'result': mean})
        return

    await send_response(send, 404, {'error': 'not found'})


async def send_response(send, status, data):
    body = json.dumps(data).encode()
    await send(
        {
            'type': 'http.response.start',
            'status': status,
            'headers': [[b'content-type', b'application/json']],
        }
    )
    await send({'type': 'http.response.body', 'body': body})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
