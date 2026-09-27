import json
from urllib.parse import parse_qs
from typing import Any, Awaitable, Callable


async def send_response(send: Callable, status: int, data: dict | None = None):
    body = json.dumps(data).encode('utf-8') if data is not None else b''
    headers = [
        (b'content-type', b'application/json'),
        (b'content-length', str(len(body)).encode('ascii')),
    ]

    await send({
        'type': 'http.response.start',
        'status': status,
        'headers': headers,
    })

    await send({
        'type': 'http.response.body',
        'body': body,
    })

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
    # TODO: Ваша реализация здесь
    if scope['type'] == 'lifespan':
        while True:
            message = await receive()
            if message['type'] == 'lifespan.startup':
                await send({'type': 'lifespan.startup.complete'})
            elif message['type'] == 'lifespan.shutdown':
                await send({'type': 'lifespan.shutdown.complete'})
                return
        return

    if scope['type'] != 'http':
        return
    path = scope['path']
    method = scope['method']

    if path == '/factorial':
        query_string = scope.get('query_string', b'').decode('utf-8')
        params = parse_qs(query_string)

        if 'n' not in params or not params['n'][0]:
            await send_response(send, 422, {"detail": "no param n"})
            return

        try:
            n = int(params['n'][0])
        except ValueError:
            await send_response(send, 422, {"detail": "param n is not int"})
            return

        if n < 0:
            await send_response(send, 400, {"detail": "param n < 0"})
            return

        ans = 1
        for i in range(2, n + 1):
            ans *= i

        await send_response(send, 200, {"result": ans})


    elif path.startswith('/fibonacci/'):
        try:
            n = int(path.split('/')[-1])
        except ValueError:
            await send_response(send, 422, {"detail": "bad param n"})
            return

        if n < 0:
            await send_response(send, 400, {"detail": "param n < 0"})
            return

        if n == 0:
            ans = 0
        elif n == 1:
            ans = 1
        else:
            a = 0
            b = 1
            for i in range(2, n + 1):
                a, b = b, a + b
            ans = b

        await send_response(send, 200, {"result": ans})


    elif path == '/mean':
        body = b''
        while True:
            message = await receive()
            if message['type'] == 'http.request':
                body += message.get('body', b'')
                if not message.get('more_body', False):
                    break

        try:
            data = json.loads(body)
            if not isinstance(data, list):
                raise ValueError
        except (json.JSONDecodeError, ValueError):
            await send_response(send, 422, {"detail": "bad body"})
            return

        if len(data) == 0:
            await send_response(send, 400, {"detail": "data is empty"})
            return

        ans = sum(data) / len(data)
        await send_response(send, 200, {"result": ans})

    else:
        await send_response(send, 404, {"detail": "Not Found"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)