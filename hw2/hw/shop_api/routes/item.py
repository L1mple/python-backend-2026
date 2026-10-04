from http import HTTPStatus

from fastapi import APIRouter, HTTPException, Query, Response

from shop_api import store
from shop_api.contracts import ItemCreateRequest, ItemPatchRequest, ItemPutRequest, ItemResponse

router = APIRouter(prefix="/item")


@router.post("", status_code=HTTPStatus.CREATED)
async def post_item(info: ItemCreateRequest, response: Response) -> ItemResponse:
    item = store.add_item(info.name, info.price)
    response.headers["location"] = f"/item/{item.id}"
    return ItemResponse.from_entity(item)


@router.get("/{id}")
async def get_item_by_id(id: int) -> ItemResponse:
    item = store.get_item(id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {id} not found")
    return ItemResponse.from_entity(item)


@router.get("")
async def get_item_list(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    show_deleted: bool = Query(False),
) -> list[ItemResponse]:
    items = store.list_items(offset, limit, min_price, max_price, show_deleted)
    return [ItemResponse.from_entity(item) for item in items]


@router.put("/{id}")
async def put_item(id: int, info: ItemPutRequest) -> ItemResponse:
    item = store.replace_item(id, info.name, info.price)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {id} not found")
    return ItemResponse.from_entity(item)


@router.patch("/{id}")
async def patch_item(id: int, info: ItemPatchRequest, response: Response) -> ItemResponse:
    existing = store.get_item(id)
    if existing is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {id} not found")

    if existing.deleted:
        response.status_code = HTTPStatus.NOT_MODIFIED
        return ItemResponse.from_entity(existing)

    item = store.patch_item(id, info.name, info.price)
    return ItemResponse.from_entity(item)


@router.delete("/{id}")
async def delete_item(id: int) -> Response:
    item = store.get_item(id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {id} not found")
    store.delete_item(id)
    return Response(status_code=HTTPStatus.OK)