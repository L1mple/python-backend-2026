from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class DBItem(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    price = Column(Float)
    deleted = Column(Boolean, default=False)

class DBCart(Base):
    __tablename__ = "carts"
    id = Column(Integer, primary_key=True, index=True)
    items = relationship("DBCartItem", back_populates="cart")

class DBCartItem(Base):
    __tablename__ = "cart_items"
    cart_id = Column(Integer, ForeignKey("carts.id"), primary_key=True)
    item_id = Column(Integer, ForeignKey("items.id"), primary_key=True)
    quantity = Column(Integer, default=1)
    
    cart = relationship("DBCart", back_populates="items")
    item = relationship("DBItem")