from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import WebSocket
from fastapi.testclient import TestClient

from shop_api.chat import ChatRoomsBroadcaster
from shop_api.main import app

# first id fits INTEGER columns, second one does not
MISSING_RECORD_IDS = [
    2_000_000_000,
    99_999_999_999,
]


@pytest.fixture()
def shop_api_client() -> TestClient:
    return TestClient(app=app)


@pytest.fixture()
def existing_item_id(
    shop_api_client: TestClient,
) -> int:
    return shop_api_client.post(
        url="/item",
        json={
            "name": "GPT-6.5 Colossus, 1M tokens of AGI",
            "price": 100.0,
        },
    ).json()["id"]


@pytest.fixture()
def existing_cart_id(
    shop_api_client: TestClient,
) -> int:
    return shop_api_client.post(url="/cart").json()["id"]


def test_cart_shows_current_name_price_and_availability_of_its_items(
    shop_api_client: TestClient,
    existing_cart_id: int,
    existing_item_id: int,
) -> None:
    shop_api_client.post(url=f"/cart/{existing_cart_id}/add/{existing_item_id}")
    shop_api_client.post(url=f"/cart/{existing_cart_id}/add/{existing_item_id}")
    shop_api_client.patch(
        url=f"/item/{existing_item_id}",
        json={
            "name": "GPT-6.5 Colossus, 1M tokens of ASI",
            "price": 30.0,
        },
    )
    cart_after_item_change = shop_api_client.get(url=f"/cart/{existing_cart_id}").json()
    shop_api_client.delete(url=f"/item/{existing_item_id}")
    cart_after_item_deletion = shop_api_client.get(url=f"/cart/{existing_cart_id}").json()

    assert cart_after_item_change["items"] == [
        {
            "id": existing_item_id,
            "name": "GPT-6.5 Colossus, 1M tokens of ASI",
            "quantity": 2,
            "available": True,
        },
    ]
    assert cart_after_item_change["price"] == 60.0
    assert cart_after_item_deletion["items"][0]["available"] is False
    assert cart_after_item_deletion["price"] == 0.0


@pytest.mark.parametrize(
    argnames="missing_cart_id",
    argvalues=MISSING_RECORD_IDS,
)
def test_get_missing_cart_returns_404(
    shop_api_client: TestClient,
    missing_cart_id: int,
) -> None:
    response = shop_api_client.get(url=f"/cart/{missing_cart_id}")

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(
    argnames="missing_record_id",
    argvalues=MISSING_RECORD_IDS,
)
def test_add_item_to_cart_returns_404_when_cart_or_item_is_missing(
    shop_api_client: TestClient,
    existing_cart_id: int,
    existing_item_id: int,
    missing_record_id: int,
) -> None:
    response_for_missing_cart = shop_api_client.post(url=f"/cart/{missing_record_id}/add/{existing_item_id}")
    response_for_missing_item = shop_api_client.post(url=f"/cart/{existing_cart_id}/add/{missing_record_id}")

    assert response_for_missing_cart.status_code == HTTPStatus.NOT_FOUND
    assert response_for_missing_item.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(
    argnames="missing_item_id",
    argvalues=MISSING_RECORD_IDS,
)
@pytest.mark.parametrize(
    argnames=("method", "request_body"),
    argvalues=[
        ("GET", None),
        ("PUT", {"name": "Claude 6 Jotunn, alignment solved", "price": 100.0}),
        ("PATCH", {"price": 100.0}),
        ("DELETE", None),
    ],
)
def test_request_to_missing_item_returns_404(
    shop_api_client: TestClient,
    missing_item_id: int,
    method: str,
    request_body: dict[str, Any] | None,
) -> None:
    response = shop_api_client.request(
        method=method,
        url=f"/item/{missing_item_id}",
        json=request_body,
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(
    argnames="invalid_price",
    argvalues=[
        -1.0,
        "NaN",
        "Infinity",
    ],
)
def test_create_item_with_invalid_price_returns_422(
    shop_api_client: TestClient,
    invalid_price: float | str,
) -> None:
    response = shop_api_client.post(
        url="/item",
        json={
            "name": "Grok 5 Leviathan, priceless",
            "price": invalid_price,
        },
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.parametrize(
    argnames="request_body_with_explicit_null",
    argvalues=[
        {"name": None},
        {"price": None},
    ],
)
def test_patch_item_with_explicit_null_returns_422(
    shop_api_client: TestClient,
    existing_item_id: int,
    request_body_with_explicit_null: dict[str, None],
) -> None:
    response = shop_api_client.patch(
        url=f"/item/{existing_item_id}",
        json=request_body_with_explicit_null,
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_chat_message_is_relayed_only_to_other_members_of_the_same_chat(
    shop_api_client: TestClient,
) -> None:
    with (
        shop_api_client.websocket_connect(url="/chat/accelerationists") as first_accelerationist,
        shop_api_client.websocket_connect(url="/chat/accelerationists") as second_accelerationist,
        shop_api_client.websocket_connect(url="/chat/doomers") as first_doomer,
        shop_api_client.websocket_connect(url="/chat/doomers") as second_doomer,
    ):
        first_accelerationist.send_text(data="AGI achieved internally")
        message_received_by_second_accelerationist = second_accelerationist.receive_text()
        second_accelerationist.send_text(data="we are so back")
        message_received_by_first_accelerationist = first_accelerationist.receive_text()
        second_doomer.send_text(data="it's over")
        message_received_by_first_doomer = first_doomer.receive_text()

    assert message_received_by_second_accelerationist.startswith("user-")
    assert message_received_by_second_accelerationist.endswith(" :: AGI achieved internally")
    # an echo to the sender would arrive before the reply
    assert message_received_by_first_accelerationist.endswith(" :: we are so back")
    # a leaked accelerationists message would arrive before the doomers one
    assert message_received_by_first_doomer.endswith(" :: it's over")


@pytest.mark.asyncio
async def test_chat_member_who_failed_to_receive_is_removed_and_others_still_get_the_message() -> None:
    chat_rooms_broadcaster = ChatRoomsBroadcaster()
    sender_websocket = AsyncMock(spec=WebSocket)
    disconnected_websocket = AsyncMock(spec=WebSocket)
    disconnected_websocket.send_text.side_effect = RuntimeError("websocket is closed")
    connected_websocket = AsyncMock(spec=WebSocket)
    for websocket in (sender_websocket, disconnected_websocket, connected_websocket):
        await chat_rooms_broadcaster.accept_and_join_chat(
            chat_name="accelerationists",
            websocket=websocket,
        )

    await chat_rooms_broadcaster.send_message_to_other_members_of_chat(
        chat_name="accelerationists",
        sender_websocket=sender_websocket,
        message="feel the AGI",
    )

    sender_websocket.send_text.assert_not_awaited()
    connected_websocket.send_text.assert_awaited_once_with("feel the AGI")
    assert chat_rooms_broadcaster.websockets_by_chat_name["accelerationists"] == [
        sender_websocket,
        connected_websocket,
    ]
    # its own handler leaves once more on exit and must not fail
    chat_rooms_broadcaster.leave_chat(
        chat_name="accelerationists",
        websocket=disconnected_websocket,
    )
