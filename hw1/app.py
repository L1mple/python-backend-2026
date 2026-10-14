import json
from urllib.parse import parse_qs
from typing import Any, Awaitable, Callable


BAD_REQUEST = None, 400
UNPROCESSABLE_ENTITY = None, 422
SUCCEFULL = lambda result: ({"result": result}, 200)


async def check_integer(n_str):
    try:
        n = int(n_str)
    except (ValueError, TypeError):
        return None
    return n


async def fibonacci(request):
    n = await check_integer(request['path_params']['n'])
    if n is None:
        return UNPROCESSABLE_ENTITY
    if n < 0:
        return BAD_REQUEST
    def fib(n):
        if n <= 1:
            return n
        a, b = 0, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b
    result = fib(n)
    return SUCCEFULL(result)


async def factorial(request):
    query_params = request['query_params']
    if 'n' not in query_params:
        return UNPROCESSABLE_ENTITY
    n = await check_integer(query_params['n'])
    if n is None:
        return UNPROCESSABLE_ENTITY
    if n < 0:
        return BAD_REQUEST
    result = 1
    for i in range(1, n + 1):
        result *= i
    return SUCCEFULL(result)


async def mean(request):
    body = request.get('body')
    if body is None or body == '':
        return UNPROCESSABLE_ENTITY
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return UNPROCESSABLE_ENTITY
    if not isinstance(data, list):
        return UNPROCESSABLE_ENTITY
    if len(data) == 0:
        return BAD_REQUEST
    try:
        numbers = [float(x) for x in data]
    except (TypeError, ValueError):
        return UNPROCESSABLE_ENTITY
    result = sum(numbers) / len(numbers)
    return SUCCEFULL(result)


async def send_json_response(send, status_code, data):
    json_bytes = json.dumps(data, ensure_ascii=False).encode('utf-8')
    await send({
        'type': 'http.response.start',
        'status': status_code,
        'headers': [
            [b'content-type', b'application/json; charset=utf-8'],
            [b'content-length', str(len(json_bytes)).encode('ascii')],
        ],
    })
    await send({
        'type': 'http.response.body',
        'body': json_bytes,
    })


def parse_path(path):
    path = path.rstrip('/')
    parts = path.split('/')
    if len(parts) == 3 and parts[1] == 'fibonacci':
        return 'fibonacci', {'n': parts[2]}
    if len(parts) == 2 and parts[1] == 'factorial':
        return 'factorial', {}
    if len(parts) == 2 and parts[1] == 'mean':
        return 'mean', {}
    return None, {}


async def read_body(receive):
    body = b''
    while True:
        message = await receive()
        body += message.get('body', b'')
        if not message.get('more_body', False):
            break
    return body


async def handle_lifespan(receive, send):
    while True:
        message = await receive()
        if message['type'] == 'lifespan.startup':
            await send({'type': 'lifespan.startup.complete'})
        elif message['type'] == 'lifespan.shutdown':
            await send({'type': 'lifespan.shutdown.complete'})
            return


HANDLERS = {
    'fibonacci': fibonacci,
    'factorial': factorial,
    'mean': mean,
}


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
        await handle_lifespan(receive, send)
        return
    if scope["type"] != "http":
        return
    path = scope['path']
    method = scope['method']
    query_string = scope['query_string']
    query_params = {k: v[0] for k, v in parse_qs(query_string.decode('utf-8')).items()}
    body_bytes = await read_body(receive)
    body = body_bytes.decode('utf-8') if len(body_bytes) > 0 else None
    endpoint, path_params = parse_path(path)
    if endpoint is None:
        await send_json_response(send, 404, {'error': 'Not Found'})
        return
    request = {
        'path': path,
        'method': method,
        'query_params': query_params,
        'path_params': path_params,
        'body': body,
    }
    handler = HANDLERS[endpoint]
    result, status_code = await handler(request)
    if result is None:
        await send_json_response(send, status_code, {'error': 'Invalid request'})
    else:
        await send_json_response(send, status_code, result)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
