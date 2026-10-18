from shop_api.core.db import Base, CommonMixin
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Boolean, String, Float


class Item(CommonMixin, Base):
    name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    price: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    cart_links: Mapped[list["CartItem"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
    )