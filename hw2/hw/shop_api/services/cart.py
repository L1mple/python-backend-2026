from sqlalchemy.orm import selectinload

from shop_api.models.cart_item import CartItem
from shop_api.models.item import Item
from shop_api.schemas.cart import CartDB, CartItemDB, CartListQuery
from shop_api.services.item import ItemService
from shop_api.models.cart import Cart
from shop_api.services.crud import CRUDBase
from sqlalchemy.ext.asyncio import AsyncSession
from shop_api.services.exceptions import CartNotFoundError
from sqlalchemy import func, select


class CartService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.crud = CRUDBase(Cart, session)
        self.item_service = ItemService(session)

    async def create_cart(self) -> Cart:
        return await self.crud.create()

    async def get_carts(self, query: CartListQuery) -> list[CartDB]:
        total_price = func.coalesce(
            func.sum(Item.price * CartItem.quantity), 0.0
        ).label("total_price")
        total_quantity = func.coalesce(
            func.sum(CartItem.quantity), 0
        ).label("total_quantity")
        selection = (
            select(Cart.id.label("cart_id"), total_price, total_quantity)
            .outerjoin(CartItem, CartItem.cart_id == Cart.id)
            .outerjoin(Item, Item.id == CartItem.item_id)
            .group_by(Cart.id)
            .order_by(Cart.id)
        )
        if query.min_price is not None:
            selection = selection.having(total_price >= query.min_price)
        if query.max_price is not None:
            selection = selection.having(total_price <= query.max_price)
        if query.min_quantity is not None:
            selection = selection.having(total_quantity >= query.min_quantity)
        if query.max_quantity is not None:
            selection = selection.having(total_quantity <= query.max_quantity)
        selection = selection.limit(query.limit).offset(query.offset)
        rows = (await self.session.execute(selection)).all()
        if not rows:
            return []
        cart_ids = [r.cart_id for r in rows]
        price_by_id = {r.cart_id: r.total_price for r in rows}
        carts = await self._load_carts_with_items(cart_ids)
        return [self._cart_to_dict(c, price_by_id[c.id]) for c in carts]

    async def get_cart_by_id(self, cart_id: int) -> CartDB:
        cart = await self._check_cart_exist(cart_id)
        db_objs = await self._load_carts_with_items([cart.id])
        cart_with_items = db_objs[0]
        return self._cart_to_dict(cart_with_items)

    async def _check_cart_exist(self, cart_id) -> Cart:
        cart = await self.crud.get_by_id(cart_id)
        if cart is None:
            raise CartNotFoundError(f"Cart with id {cart_id} not found")
        return cart

    async def _load_carts_with_items(self, cart_ids: list[int]) -> list[Cart]:
        db_objs = await self.session.execute(
            select(Cart)
            .where(Cart.id.in_(cart_ids))
            .options(selectinload(Cart.items).selectinload(CartItem.item))
            .order_by(Cart.id)
        )
        return list(db_objs.scalars().all())

    async def _get_cart_item(self, cart_id: int, item_id: int) -> CartItem | None:
        db_obj = await self.session.execute(
            select(CartItem).where(
                CartItem.cart_id == cart_id,
                CartItem.item_id == item_id,
            )
        )
        return db_obj.scalars().first()

    async def add_item_to_cart(self, cart_id: int, item_id: int) -> CartDB:
        cart = await self._check_cart_exist(cart_id)
        item = await self.item_service.get_item_by_id(item_id)
        cart_item = await self._get_cart_item(cart.id, item.id)
        if cart_item is None:
            cart_item = CartItem(cart_id=cart.id, item_id=item.id)
            self.session.add(cart_item)
        else:
            cart_item.quantity += 1
        await self.session.flush()
        db_objs = await self._load_carts_with_items([cart.id])
        cart_with_items = db_objs[0]
        return self._cart_to_dict(cart_with_items)

    def _cart_to_dict(self, cart: Cart, price: float | None = None) -> CartDB:
        items_out: list[CartItemDB] = []
        cart_price = price if price is not None else 0.0
        for link in cart.items:
            item = link.item
            items_out.append(
                CartItemDB(
                    id=item.id,
                    name=item.name,
                    quantity=link.quantity,
                    available=not item.deleted,
                )
            )
            if price is None:
                cart_price += item.price * link.quantity
        return CartDB(id=cart.id, items=items_out, price=cart_price)
