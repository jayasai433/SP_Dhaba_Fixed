from typing import Optional
from pydantic import BaseModel, Field

class PurchaseIn(BaseModel):
    item_id:        str
    date:           str           # YYYY-MM-DD
    quantity:       float = Field(gt=0)
    price_per_unit: float = Field(ge=0)

class UsageIn(BaseModel):
    item_id:       str
    date:          str
    quantity_used: float = Field(gt=0)
    notes:         Optional[str] = ""

class SalesIn(BaseModel):
    date:          str
    lunch_amount:  float = Field(ge=0)
    dinner_amount: float = Field(ge=0)
    other_amount:  float = Field(ge=0)
    notes:         Optional[str] = ""

class ExpenseIn(BaseModel):
    date:        str
    category:    str
    description: Optional[str] = ""
    amount:      float = Field(gt=0)

class VoidIn(BaseModel):
    reason: str
