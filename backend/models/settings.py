from typing import Optional
from pydantic import BaseModel, Field


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ExpenseCategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class BusinessProfileIn(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    logo_base64: Optional[str] = None
