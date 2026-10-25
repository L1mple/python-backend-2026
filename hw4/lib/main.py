from typing import Any

from fastapi import FastAPI,  Query, HTTPException, Depends
from prometheus_fastapi_instrumentator import Instrumentator
from fastapi.responses import JSONResponse
from http import HTTPStatus
from pydantic import BaseModel, ConfigDict

from .db import lifespan, get_db_connection

app = FastAPI(title="Shop API", lifespan=lifespan)

Instrumentator().instrument(app).expose(app)

class ItemToModify(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str | None = None
    price: float | None = None

class ItemToCreate(BaseModel): # сущность товара
    model_config = ConfigDict(extra='forbid')

    name: str
    price: float

class Item(ItemToCreate): # сущность товара
    model_config = ConfigDict(extra='forbid')

    id: int
    deleted: bool

class CartItem(BaseModel): # сущность товаров в корзине
    model_config = ConfigDict(extra='forbid')

    id: int
    name: str
    quantity: int
    available: bool

class Cart(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: int
    items: list[CartItem]
    price: float

@app.post('/cart')
async def create_cart(conn = Depends(get_db_connection)) -> Cart:
    async with conn.cursor() as cur:
        await cur.execute('''
            INSERT INTO carts DEFAULT VALUES
            RETURNING id;
        ''')
        cart = await cur.fetchone()

    return JSONResponse(
        content=Cart(id=cart[0], items=[], price=0).model_dump(),
        status_code=HTTPStatus.CREATED,
        headers={"Location": f"/cart/{cart[0]}"}
    )

@app.get('/cart/{id}')
async def get_cart(id: int, conn = Depends(get_db_connection)) -> Cart:
    async with conn.cursor() as cur:
        await cur.execute('''
        SELECT carts.id, items.id, items.name, cart_items.quantity, items.deleted, items.price
        FROM carts
        LEFT JOIN cart_items ON carts.id = cart_items.cart_id
        LEFT JOIN items ON cart_items.item_id = items.id
        WHERE carts.id = %s;
        ''', [id])
        rows = await cur.fetchall()
        # no cart -> []
        # empty cart -> [[carts.id, null, null, null, null, null]]
        # not empty cart -> [
        #   [carts.id, item1.id, item1.name, item1.quantity, item1.deleted, item1.price],
        #   [carts.id, item2.id, item2.name, item2.quantity, item2.deleted, item2.price],
        #   [ ... ]
        # ]

        if not rows:
            raise HTTPException(status_code=404)

        items = []
        price = 0.0
        for row in rows:
            if row[1] is None:
                continue
            items.append(CartItem(id=row[1], name=row[2], quantity=row[3], available=not row[4]))
            price += row[5] * row[3]

        return Cart(id=rows[0][0], items=items, price=price)

@app.get('/cart')
async def get_carts(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, gt=0),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    min_quantity: int | None = Query(default=None, ge=0),
    max_quantity: int | None = Query(default=None, ge=0),
    conn = Depends(get_db_connection)
) -> list[Cart]:
    async with conn.cursor() as cur:
        await cur.execute('''
            WITH filtered_carts AS (
                SELECT carts.id, COALESCE(SUM(items.price * cart_items.quantity), 0.0) AS price
                FROM carts
                LEFT JOIN cart_items ON carts.id = cart_items.cart_id
                LEFT JOIN items ON cart_items.item_id = items.id
                WHERE 1 = 1
                '''
                + '''
                GROUP BY carts.id
                HAVING 1 = 1
                '''
                + (' AND COALESCE(SUM(items.price * cart_items.quantity), 0.0) >= %s ' if min_price is not None else '')
                + (' AND COALESCE(SUM(items.price * cart_items.quantity), 0.0) <= %s ' if max_price is not None else '')
                + (' AND COALESCE(SUM(cart_items.quantity), 0) >= %s ' if min_quantity is not None else '')
                + (' AND COALESCE(SUM(cart_items.quantity), 0) <= %s ' if max_quantity is not None else '')
                + '''
                ORDER BY carts.id ASC
                LIMIT %s OFFSET %s
            )
            SELECT filtered_carts.id, filtered_carts.price,
                    items.id, items.name, cart_items.quantity, items.deleted
            FROM filtered_carts
            LEFT JOIN cart_items ON filtered_carts.id = cart_items.cart_id
            LEFT JOIN items ON cart_items.item_id = items.id
            ORDER BY filtered_carts.id ASC, items.id ASC;
        ''', [
            x for x in [min_price, max_price, min_quantity, max_quantity, limit, offset]
            if x is not None
        ])

        # one empty, one with two items =>
        # [
            # [cart1.id, cart1.price, None, None, None, None],
            # [cart2.id, cart2.price, item1.id, item1....],
            # [cart2.id, cart2.price, item2.id, item2....],
        # ]
        carts: list[Cart] = []

        current_cart: Cart | None = None

        for cart_data in await cur.fetchall():
            cart_id = cart_data[0]
            if current_cart is not None and cart_id != current_cart.id:
                carts.append(current_cart)
                current_cart = None

            if current_cart is None:
                current_cart = Cart(id=cart_id, items=[], price=cart_data[1])

            if cart_data[2] is not None:
                current_cart.items.append(
                    CartItem(
                        id=cart_data[2],
                        name=cart_data[3],
                        quantity=cart_data[4],
                        available=not cart_data[5],
                    )
                )

        if current_cart is not None:
            carts.append(current_cart)

        return carts


@app.post('/cart/{cart_id}/add/{item_id}')
async def add_item_to_cart(cart_id: int, item_id: int, conn = Depends(get_db_connection)) -> None:
    async with conn.transaction():
        async with conn.cursor() as cur:
            await cur.execute('SELECT id FROM items WHERE id = %s AND NOT deleted', [item_id])
            if await cur.fetchone() is None:
                raise HTTPException(status_code=404)

            await cur.execute('SELECT id FROM carts WHERE id = %s FOR UPDATE', [cart_id])
            if await cur.fetchone() is None:
                raise HTTPException(status_code=404)

            await cur.execute('''
                INSERT INTO cart_items(item_id, cart_id, quantity)
                VALUES (%s, %s, 1)
                ON CONFLICT (item_id, cart_id)
                DO UPDATE
                SET quantity = cart_items.quantity + 1
            ''', [item_id, cart_id])

@app.post('/item')
async def create_item(item: ItemToCreate, conn = Depends(get_db_connection)) -> Item:
    async with conn.cursor() as cur:
        await cur.execute('''
            INSERT INTO items(name, price, deleted)
            VALUES(%s, %s, false)
            RETURNING id;
        ''', [item.name, item.price])
        item_data = await cur.fetchone()

    created_item = Item(id=item_data[0], name=item.name, price=item.price, deleted=False)

    return JSONResponse(
        status_code=HTTPStatus.CREATED,
        content=created_item.model_dump(),
        headers={"Location": f"/item/{item_data[0]}"}
    )

@app.get('/item/{id}')
async def get_item(id: int, conn = Depends(get_db_connection)) -> Item:
    async with conn.cursor() as cur:
        await cur.execute("SELECT id, name, price, deleted FROM items WHERE id = %s;", [id])
        row = await cur.fetchone()

        if not row or row[3]:
            raise HTTPException(status_code=404)
        return Item(id=row[0], name=row[1], price=row[2], deleted=row[3])


@app.get('/item')
async def get_items(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, gt=0),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None =Query(default=None, ge=0),
    show_deleted: bool = False,
    conn = Depends(get_db_connection)
) -> list[Item]:
    async with conn.cursor() as cur:
        await cur.execute('''
            SELECT id, name, price, deleted
            FROM items
            WHERE 1 = 1
                '''
                + (' AND price >= %s ' if min_price is not None else '')
                + (' AND price <= %s ' if max_price is not None else '')
                + (' AND NOT deleted ' if not show_deleted else '')
                + '''
            ORDER BY id ASC
            LIMIT %s OFFSET %s;
        ''', [
            x for x in [min_price, max_price, limit, offset]
            if x is not None
        ])

        items: list[Item] = []

        for item_data in await cur.fetchall():
            items.append(
                Item(
                    id=item_data[0],
                    name=item_data[1],
                    price=item_data[2],
                    deleted=item_data[3]
                ))

        return items


@app.put('/item/{id}')
async def replace_item(id: int, replacing_item: ItemToCreate, conn = Depends(get_db_connection)) -> Item:
    async with conn.cursor() as cur:
        await cur.execute('''
            UPDATE items
            SET name = %s, price = %s
            WHERE id = %s AND NOT deleted
            RETURNING id
        ''', [replacing_item.name, replacing_item.price, id])
        returning_id = await cur.fetchone()

    if returning_id is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

    return Item(id=id, name=replacing_item.name, price=replacing_item.price, deleted=False)

@app.patch('/item/{id}')
async def modify_item(id: int, modifying_item: ItemToModify, conn = Depends(get_db_connection)) -> Item:
    if modifying_item.name is None and modifying_item.price is None:
        try:
            return await get_item(id, conn)
        except HTTPException:
            raise HTTPException(status_code=HTTPStatus.NOT_MODIFIED)

    async with conn.cursor() as cur:
        await cur.execute('''
            UPDATE items
            SET
            '''
            + ', '.join(s for s in [
                'name = %s' if modifying_item.name is not None else None,
                'price = %s' if modifying_item.price is not None else None,
            ] if s)
            + '''
            WHERE id = %s AND NOT deleted
            RETURNING id, name, price, deleted
        ''',
        [x for x in [
            modifying_item.name,
            modifying_item.price,
            id
        ] if x is not None]
        )
        updated_item = await cur.fetchone()

    if updated_item is None:
        raise HTTPException(status_code=HTTPStatus.NOT_MODIFIED)

    return Item(
        id=updated_item[0],
        name=updated_item[1],
        price=updated_item[2],
        deleted=updated_item[3],
    )

@app.delete('/item/{id}')
async def delete_item(id: int, conn = Depends(get_db_connection)) -> None:
    async with conn.cursor() as cur:
        await cur.execute('''
            UPDATE items
            SET deleted = true
            WHERE id = %s AND NOT deleted;
        ''', [id])
