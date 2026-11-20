from pydantic import BaseModel
from typing import Optional


class ProductBase(BaseModel):
    name: str
    category: Optional[str] = None
    buying_price: float
    selling_price: float
    stock: int


class ProductCreate(ProductBase):
    pass


class ProductResponse(ProductBase):
    id: int

    class Config:
        from_attributes = True