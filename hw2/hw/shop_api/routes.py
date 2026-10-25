from typing import Optional

from shop_api.contracts import Cart, Item, ItemCreate, ItemPatch
from shop_api.queries import (
    build_cart_response,
    create_cart,
    get_cart,
    get_carts,
    add_item_to_cart,
    create_item,
    get_item,
    get_items,
    update_item,
    patch_item,
    soft_delete_item,
)
from fastapi import status, Response, Query, APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from shop_api.database import get_db

router_cart = APIRouter(prefix="/cart")


@router_cart.post("/", status_code=status.HTTP_201_CREATED)
async def post_cart_endpoint(
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    cart = await create_cart(session)
    response.headers["Location"] = f"/cart/{cart.id}"
    return {"id": cart.id}


@router_cart.get("/{cart_id}")
async def get_cart_endpoint(
    cart_id: int,
    session: AsyncSession = Depends(get_db),
) -> Cart:
    cart = await get_cart(session, cart_id)
    if cart is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart not found",
        )
    return build_cart_response(session, cart)


@router_cart.get("/", response_model=list[Cart])
async def get_carts_endpoint(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, gt=0),
    min_price: Optional[float] = Query(default=None, ge=0),
    max_price: Optional[float] = Query(default=None, ge=0),
    min_quantity: Optional[int] = Query(default=None, ge=0),
    max_quantity: Optional[int] = Query(default=None, ge=0),
    session: AsyncSession = Depends(get_db),
) -> list[Cart]:
    return await get_carts(
        session, offset, limit, min_price, max_price, min_quantity, max_quantity
    )


@router_cart.post(
    "/{cart_id}/add/{item_id}",
    response_model=Cart,
    status_code=status.HTTP_200_OK,
)
async def add_item_to_cart_endpoint(
    cart_id: int,
    item_id: int,
    session: AsyncSession = Depends(get_db),
) -> Cart:
    return await add_item_to_cart(session, cart_id, item_id)


router_item = APIRouter(prefix="/item")


@router_item.post("/", response_model=Item, status_code=status.HTTP_201_CREATED)
async def create_item_endpoint(
    response: Response,
    item_data: ItemCreate,
    session: AsyncSession = Depends(get_db),
) -> Item:
    item = await create_item(session, item_data.name, item_data.price)
    response.headers["Location"] = f"/item/{item.id}"
    return item


@router_item.get("/{item_id}", response_model=Item)
async def get_item_endpoint(
    item_id: int,
    session: AsyncSession = Depends(get_db),
) -> Item:
    item = await get_item(session, item_id)
    if item is None or item.deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )
    return item


@router_item.get("/", response_model=list[Item])
async def get_items_endpoint(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, gt=0),
    min_price: Optional[float] = Query(default=None, ge=0),
    max_price: Optional[float] = Query(default=None, ge=0),
    show_deleted: bool = Query(default=False),
    session: AsyncSession = Depends(get_db),
) -> list[Item]:
    return await get_items(session, offset, limit, min_price, max_price, show_deleted)


@router_item.put("/{item_id}", response_model=Item)
async def update_item_endpoint(
    item_id: int,
    item_data: ItemCreate,
    session: AsyncSession = Depends(get_db),
) -> Item:
    return await update_item(session, item_id, item_data.name, item_data.price)


@router_item.patch("/{item_id}", response_model=None)
async def patch_item_endpoint(
    item_id: int,
    item_data: ItemPatch,
    session: AsyncSession = Depends(get_db),
) -> Response | Item:
    item, not_modified = await patch_item(
        session, item_id, item_data.model_dump(exclude_unset=True)
    )
    if not_modified:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED)
    return item


@router_item.delete("/{item_id}")
async def delete_item_endpoint(
    item_id: int,
    session: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    await soft_delete_item(session, item_id)
    return {"deleted": True}
