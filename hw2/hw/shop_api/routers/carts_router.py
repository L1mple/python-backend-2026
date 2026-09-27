from typing import Annotated

from fastapi import APIRouter
from fastapi.params import Query
from starlette import status
from starlette.responses import JSONResponse

from shop_api.deps import CartServiceDep
from shop_api.schema import CartFiltersSchema, CartSchema

router = APIRouter(prefix='/cart', tags=['carts'])


@router.get('/')
async def get_all_carts(filters: Annotated[CartFiltersSchema, Query()],
                        service: CartServiceDep) -> list[CartSchema]:
    """Get all carts with optional filtering."""
    return service.get_all(filters)


@router.get('/{cart_id}')
async def get_cart(cart_id: int,
                   service: CartServiceDep) -> CartSchema:
    """Get a cart by its ID."""
    return service.get_cart(cart_id)


@router.post('/', status_code=status.HTTP_201_CREATED, response_model=CartSchema)
async def create_cart(service: CartServiceDep):
    """Create a cart item."""
    cart = service.create_cart()
    return JSONResponse(
        content=cart.model_dump(),
        status_code=status.HTTP_201_CREATED,
        headers={"Location": f"/cart/{cart.id}"}
    )


@router.post('/{cart_id}/add/{item_id}')
async def add_item_to_cart(cart_id: int, item_id: int,
                           service: CartServiceDep) -> CartSchema:
    """Add item to existing cart."""
    return service.add_item(cart_id, item_id)
