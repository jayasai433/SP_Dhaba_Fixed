from typing import Optional
from pydantic import BaseModel, Field

class CategoryIn(BaseModel):
    name: str

class UnitIn(BaseModel):
    name: str

class BusinessProfileIn(BaseModel):
    name:         Optional[str] = None
    address:      Optional[str] = None
    phone:        Optional[str] = None
    logo_base64:  Optional[str] = None

class ExpenseCategoryIn(BaseModel):
    name: str
