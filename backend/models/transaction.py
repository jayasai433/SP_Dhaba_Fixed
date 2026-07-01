import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator

MAX_AMOUNT = 999_999.99  # Cap for any single line entry.


def _validate_date(v: str) -> str:
    """YYYY-MM-DD, not in the future (compared against IST, not UTC)."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        raise ValueError("Date must be in YYYY-MM-DD format")
    from datetime import date as _date, datetime
    import pytz
    ist = pytz.timezone("Asia/Kolkata")
    today_ist = datetime.now(ist).date()
    entry_date = _date.fromisoformat(v)
    if entry_date > today_ist:
        raise ValueError("Future dates are not allowed for entries")
    return v


def _validate_id(v: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9_\-]{1,100}", v):
        raise ValueError("Invalid ID format")
    return v


def _sanitize_text(v: str) -> str:
    v = re.sub(r"<script[^>]*>.*?</script>", "", v, flags=re.IGNORECASE | re.DOTALL)
    v = re.sub(r"<[^>]+on\w+\s*=", "<", v, flags=re.IGNORECASE)
    v = re.sub(r"javascript:", "", v, flags=re.IGNORECASE)
    return v.strip()


class PurchaseIn(BaseModel):
    """
    A purchase line.

    unit + unit_conversion_factor let us record eggs as "1 tray" instead of
    "30 pieces" while still persisting base_quantity=30 for later stock math.
    """
    item_id: str = Field(min_length=1, max_length=100)
    date: str = Field(min_length=10, max_length=10)
    quantity: float = Field(gt=0, le=100_000)
    unit: str = Field(min_length=1, max_length=50,
                      description="The unit chosen for this transaction. Must exist in the item's units list.")
    unit_conversion_factor: float = Field(
        gt=0, le=100_000,
        description="Copy of the unit's conversion factor at time of entry. Persisted so historical data"
                    " stays correct even if the item's unit list changes later.",
    )
    price_per_unit: float = Field(gt=0, le=MAX_AMOUNT,
                                  description="Price for one of the chosen unit.")
    notes: Optional[str] = Field(default="", max_length=500)

    @field_validator("date")
    @classmethod
    def _v_date(cls, v):
        return _validate_date(v)

    @field_validator("item_id")
    @classmethod
    def _v_id(cls, v):
        return _validate_id(v)

    @field_validator("notes", "unit")
    @classmethod
    def _v_text(cls, v):
        return _sanitize_text(v) if v else v


class SalesIn(BaseModel):
    """
    Daily aggregate sales (no line items in this phase).
    One entry per date is enforced at the DB level (unique index on date).
    """
    date: str = Field(min_length=10, max_length=10)
    lunch_amount: float = Field(ge=0, le=MAX_AMOUNT)
    dinner_amount: float = Field(ge=0, le=MAX_AMOUNT)
    other_amount: float = Field(ge=0, le=MAX_AMOUNT)
    notes: Optional[str] = Field(default="", max_length=500)

    @field_validator("date")
    @classmethod
    def _v_date(cls, v):
        return _validate_date(v)

    @field_validator("notes")
    @classmethod
    def _v_notes(cls, v):
        return _sanitize_text(v) if v else v


class ExpenseIn(BaseModel):
    date: str = Field(min_length=10, max_length=10)
    category: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default="", max_length=500)
    amount: float = Field(gt=0, le=MAX_AMOUNT)

    @field_validator("date")
    @classmethod
    def _v_date(cls, v):
        return _validate_date(v)

    @field_validator("description", "category")
    @classmethod
    def _v_text(cls, v):
        return _sanitize_text(v) if v else v


class VoidIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def _v_reason(cls, v):
        return _sanitize_text(v)
