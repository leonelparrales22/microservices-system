from sqlalchemy import Column, Integer, String, Boolean, Float
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    in_stock = Column(Boolean, default=True)
    quantity = Column(Integer, default=0)
    price = Column(Float, default=0.0)
