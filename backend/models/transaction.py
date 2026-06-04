import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator

MAX_AMOUNT = 999_999.99  # Max ₹9.99 lakh per entry — reasonable for a dhaba

def _validate_date(v: str) -> str:
    """Enforce YYYY-MM-DD format."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        raise ValueError("Date must be in YYYY-MM-DD format")
    return v

class PurchaseIn(BaseModel):
    item_id:        str = Field(min_length=1, max_length=100)
    date:           str = Field(min_length=10, max_length=10)
    quantity:       float = Field(gt=0, le=100_000)
    price_per_unit: float = Field(ge=0, le=MAX_AMOUNT)

    @field_validator("date")
    @classmethod
    def validate_date(cls, v): return _validate_date(v)

class UsageIn(BaseModel):
    item_id:       str = Field(min_length=1, max_length=100)
    date:          str = Field(min_length=10, max_length=10)
    quantity_used: float = Field(gt=0, le=100_000)
    notes:         Optional[str] = Field(default="", max_length=500)

    @field_validator("date")
    @classmethod
    def validate_date(cls, v): return _validate_date(v)

class SalesIn(BaseModel):
    date:          str = Field(min_length=10, max_length=10)
    lunch_amount:  float = Field(ge=0, le=MAX_AMOUNT)
    dinner_amount: float = Field(ge=0, le=MAX_AMOUNT)
    other_amount:  float = Field(ge=0, le=MAX_AMOUNT)
    notes:         Optional[str] = Field(default="", max_length=500)

    @field_validator("date")
    @classmethod
    def validate_date(cls, v): return _validate_date(v)

class ExpenseIn(BaseModel):
    date:        str = Field(min_length=10, max_length=10)
    category:    str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default="", max_length=500)
    amount:      float = Field(gt=0, le=MAX_AMOUNT)

    @field_validator("date")
    @classmethod
    def validate_date(cls, v): return _validate_date(v)

class VoidIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500,
                        description="Void reason must be at least 3 characters")
