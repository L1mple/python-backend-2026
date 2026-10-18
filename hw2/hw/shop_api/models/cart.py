from sqlalchemy import Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shop_api.core.db import Base, CommonMixin


class Cart(CommonMixin, Base):
    items: Mapped[list["CartItem"]] = relationship(
        back_populates="cart",
        cascade="all, delete-orphan",
    )
