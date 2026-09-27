from typing import Annotated

from fastapi import APIRouter
from fastapi.params import Query
from starlette import status
from starlette.responses import JSONResponse

from shop_api.deps import ItemServiceDep
from shop_api.exceptions import NotFoundError
from shop_api.schema import ItemSchema, ItemCreateSchema, ItemPatchSchema, ItemFiltersSchema

router = APIRouter(prefix='/item', tags=['items'])


@router.get('/')
async def get_all_items(filters: Annotated[ItemFiltersSchema, Query()],
                        service: ItemServiceDep) -> list[ItemSchema]:
    """Get all items with optional filtering."""
    return service.get_all(filters)


@router.get('/{item_id}')
async def get_item(item_id: int,
                   service: ItemServiceDep) -> ItemSchema:
    """Get an item by its ID."""
    return service.get_item(item_id)


@router.post('/', status_code=status.HTTP_201_CREATED)
async def create_item(item: ItemCreateSchema,
                      service: ItemServiceDep) -> ItemSchema:
    """Create a new item."""
    return service.create_item(item)


@router.put('/{item_id}')
async def update_item(item_id: int, item: ItemCreateSchema,
                      service: ItemServiceDep) -> ItemSchema:
    """Update an existing item."""
    return service.update_item(item_id, item)


@router.patch('/{item_id}', response_model=ItemSchema)
async def patch_item(item_id: int, item: ItemPatchSchema,
                     service: ItemServiceDep):
    """Partially update an existing item."""
    try:
        return service.update_item(item_id, item)
    except NotFoundError:
        return JSONResponse(
            content={'message': 'Item not modified.'},
            status_code=status.HTTP_304_NOT_MODIFIED,
        )


@router.delete('/{item_id}')
async def delete_item(item_id: int,
                      service: ItemServiceDep) -> None:
    """Delete an item by its ID."""
    service.delete_item(item_id)
