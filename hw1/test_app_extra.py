import asyncio
import json

import pytest
from async_asgi_testclient import TestClient

from app import application


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('path', 'result'),
    [('/factorial?n=0', 1), ('/factorial?n=5', 120),
     ('/fibonacci/0', 0), ('/fibonacci/1', 1),
     ('/fibonacci/10', 55), ('/fibonacci/100', 354224848179261915075),
     ('/mean?numbers=1,2,3', 2), ('/mean?numbers=-1,2.5,6', 2.5)],
)
async def test_exact_results(path, result):
    async with TestClient(application) as client:
        response = await client.get(path)
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/json'
    assert response.json() == {'result': result}


@pytest.mark.asyncio
@pytest.mark.parametrize('value', [None, {}, '123', [True], ['2'], [None], [float('inf')], [float('nan')]])
async def test_invalid_mean_body(value):
    async with TestClient(application) as client:
        response = await client.get('/mean', json=value)
    assert response.status_code == 422
    assert 'error' in response.json()


@pytest.mark.asyncio
@pytest.mark.parametrize('path', [
    '/factorial?n=1.5', '/factorial?n=1&n=2', '/fibonacci',
    '/fibonacci/1/2', '/mean?numbers=', '/mean?numbers=1,,2',
    '/mean?numbers=NaN', '/mean?numbers=inf', '/mean?numbers=abc',
])
async def test_invalid_parameters(path):
    async with TestClient(application) as client:
        response = await client.get(path)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_mean_body_takes_precedence():
    async with TestClient(application) as client:
        response = await client.get('/mean?numbers=invalid', json=[10, 20])
    assert response.status_code == 200
    assert response.json() == {'result': 15}


@pytest.mark.asyncio
async def test_malformed_body_does_not_fall_back_to_query():
    async with TestClient(application) as client:
        response = await client.get('/mean?numbers=1,2', data='[bad')
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_unsupported_method():
    async with TestClient(application) as client:
        response = await client.post('/factorial?n=5')
    assert response.status_code == 422


def test_chunked_body():
    messages = iter([
        {'type': 'http.request', 'body': b'[1,', 'more_body': True},
        {'type': 'http.request', 'body': b'2,3]', 'more_body': False},
    ])
    sent = []

    async def receive():
        return next(messages)

    async def send(message):
        sent.append(message)

    asyncio.run(application({'type': 'http', 'method': 'GET', 'path': '/mean', 'query_string': b''}, receive, send))
    assert sent[0]['status'] == 200
    assert json.loads(sent[1]['body']) == {'result': 2}


def test_disconnected_body_does_not_send_response():
    async def receive():
        return {'type': 'http.disconnect'}

    sent = []

    async def send(message):
        sent.append(message)

    asyncio.run(application({'type': 'http', 'method': 'GET', 'path': '/mean', 'query_string': b''}, receive, send))
    assert sent == []


@pytest.mark.asyncio
async def test_mean_large_integer_cancellation():
    async with TestClient(application) as client:
        response = await client.get('/mean', json=[10**400, -(10**400)])
    assert response.status_code == 200
    assert response.json() == {'result': 0}
