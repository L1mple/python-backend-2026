import pytest
from hw2.hw.shop_api.websocket import Chat, chats


@pytest.mark.asyncio
async def test_sender_does_not_get_own_message(mocker):
    sender = mocker.AsyncMock()
    receiver = mocker.AsyncMock()
    chat = Chat(users=[sender, receiver])

    await chat.send_message(sender, "привет")

    receiver.send_text.assert_awaited_once_with("привет")
    sender.send_text.assert_not_awaited()


def test_chat(client):
    with client.websocket_connect("/chat/room") as first:
        with client.websocket_connect("/chat/room") as second:
            first.send_text("привет")
            username, text = second.receive_text().split(" :: ")

            assert len(username) == 8
            assert text == "привет"
            assert len(chats["room"].users) == 2

    assert "room" not in chats
