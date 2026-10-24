import re
from http import HTTPStatus

from fastapi.testclient import TestClient

MESSAGE_RE = re.compile(r'^(?P<username>[a-z]{10}) :: (?P<text>.*)$')


def parse(message: str) -> tuple[str, str]:
    match = MESSAGE_RE.match(message)
    assert match, message
    return match['username'], match['text']


def test_chat_page(client: TestClient) -> None:
    response = client.get('/chat')

    assert response.status_code == HTTPStatus.OK
    assert response.headers['content-type'].startswith('text/html')


def test_broadcast_inside_room(client: TestClient) -> None:
    with client.websocket_connect('/chat/room') as alice, client.websocket_connect('/chat/room') as bob:
        alice.send_text('hello')

        alice_name, text = parse(alice.receive_text())
        assert text == 'hello'
        assert parse(bob.receive_text()) == (alice_name, 'hello')

        bob.send_text('hi')

        bob_name, _ = parse(alice.receive_text())
        assert parse(bob.receive_text()) == (bob_name, 'hi')
        assert bob_name != alice_name


def test_rooms_are_isolated(client: TestClient) -> None:
    with client.websocket_connect('/chat/first') as first, client.websocket_connect('/chat/second') as second:
        first.send_text('for first')
        second.send_text('for second')

        # Если бы сообщение из first дошло до second, оно пришло бы раньше собственного.
        assert parse(first.receive_text())[1] == 'for first'
        assert parse(second.receive_text())[1] == 'for second'


def test_disconnected_user_is_unsubscribed(client: TestClient) -> None:
    with client.websocket_connect('/chat/leave') as stayer:
        with client.websocket_connect('/chat/leave') as leaver:
            leaver.send_text('bye')
            stayer.receive_text()
            leaver.receive_text()

        stayer.send_text('anyone?')

        assert parse(stayer.receive_text())[1] == 'anyone?'
