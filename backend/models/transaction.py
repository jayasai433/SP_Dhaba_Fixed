import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator

MAX_AMOUNT = 999_999.99  # Max ₹9.99 lakh per entry — reasonable for a dhaba

def _validate_date(v: str) -> str:
    """Enforce YYYY-MM-DD format and reject future dates."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        raise ValueError("Date must be in YYYY-MM-DD format")
    try:
        from datetime import date as _date
        entry_date = _date.fromisoformat(v)
        if entry_date > _date.today():
            raise ValueError("Future dates are not allowed for financial entries")
    except ValueError as e:
        raise e
    return v

def _validate_item_id(v: str) -> str:
    """Only allow safe item IDs — alphanumeric, hyphens, underscores."""
    if not re.fullmatch(r"[a-zA-Z0-9_\-]{1,100}", v):
        raise ValueError("Invalid item ID format")
    return v

def _sanitize_text(v: str) -> str:
    """Strip dangerous HTML/script tags from text fields."""
    # Remove script tags and event handlers
    v = re.sub(r"<script[^>]*>.*?</script>", "", v, flags=re.IGNORECASE | re.DOTALL)
    v = re.sub(r"<[^>]+on\w+\s*=", "<", v, flags=re.IGNORECASE)
    v = re.sub(r"javascript:", "", v, flags=re.IGNORECASE)
    return v.strip()

class PurchaseIn(BaseModel):
    item_id:        str = Field(min_length=1, max_length=100)
    date:           str = Field(min_length=10, max_length=10)
    quantity:       float = Field(gt=0, le=100_000)
    price_per_unit: float = Field(ge=0, le=MAX_AMOUNT)
    notes:          str = Field(default="", max_length=500)

    @field_validator("date")
    @classmethod
    def validate_date(cls, v): return _validate_date(v)

    @field_validator("item_id")
    @classmethod
    def validate_item_id(cls, v): return _validate_item_id(v)

    @field_validator("notes")
    @classmethod
    def sanitize_notes(cls, v): return _sanitize_text(v) if v else v

class UsageIn(BaseModel):
    item_id:       str = Field(min_length=1, max_length=100)
    date:          str = Field(min_length=10, max_length=10)
    quantity_used: float = Field(gt=0, le=100_000)
    notes:         Optional[str] = Field(default="", max_length=500)

    @field_validator("date")
    @classmethod
    def validate_date(cls, v): return _validate_date(v)

    @field_validator("item_id")
    @classmethod
    def validate_item_id(cls, v): return _validate_item_id(v)

    @field_validator("notes")
    @classmethod
    def sanitize_notes(cls, v): return _sanitize_text(v) if v else v

class SalesIn(BaseModel):
    date:          str = Field(min_length=10, max_length=10)
    lunch_amount:  float = Field(ge=0, le=MAX_AMOUNT)
    dinner_amount: float = Field(ge=0, le=MAX_AMOUNT)
    other_amount:  float = Field(ge=0, le=MAX_AMOUNT)
    notes:         Optional[str] = Field(default="", max_length=500)

    @field_validator("date")
    @classmethod
    def validate_date(cls, v): return _validate_date(v)

    @field_validator("notes")
    @classmethod
    def sanitize_notes(cls, v): return _sanitize_text(v) if v else v

class ExpenseIn(BaseModel):
    date:        str = Field(min_length=10, max_length=10)
    category:    str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default="", max_length=500)
    amount:      float = Field(gt=0, le=MAX_AMOUNT)

    @field_validator("date")
    @classmethod
    def validate_date(cls, v): return _validate_date(v)

    @field_validator("description")
    @classmethod
    def sanitize_desc(cls, v): return _sanitize_text(v) if v else v

    @field_validator("category")
    @classmethod
    def sanitize_cat(cls, v): return _sanitize_text(v) if v else v

class VoidIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500,
                        description="Void reason must be at least 3 characters")

    @field_validator("reason")
    @classmethod
    def sanitize_reason(cls, v): return _sanitize_text(v)
