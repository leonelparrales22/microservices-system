from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime
from sqlalchemy.orm import declarative_base
import datetime

Base = declarative_base()


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    in_stock = Column(Boolean, default=True)
    quantity = Column(Integer, default=0)
    price = Column(Float, default=0.0)


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String, unique=True, nullable=False)
    product_id = Column(String, nullable=False)
    quantity_ordered = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String, default="processed")
