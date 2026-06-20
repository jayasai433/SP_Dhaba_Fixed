"""
Wastage & Supplier models.

Wastage log:  explicit owner-recorded entries with item / qty / reason / date.
              Separate from closing-stock variance (which is *derived* wastage).
              This is the *intentional* log so admins/staff can capture
              spoilage, breakage, accidents etc. with a documented reason.

Supplier:     simple CRUD for the dhaba vendor directory. Linked to purchases
              via optional `supplier_id` field on PurchaseIn (kept optional so
              existing purchases continue to work).
"""
import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator


def _validate_date(v: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        raise ValueError("Date must be in YYYY-MM-DD format")
    from core.utils import today_ist
    from datetime import date as _date
    if _date.fromisoformat(v) > today_ist():
        raise ValueError("Future dates are not allowed")
    return v


def _sanitize(v: str) -> str:
    v = re.sub(r"<[^>]+>", "", v or "")
    return v.strip()


# ── Wastage ───────────────────────────────────────────────────────────────
WASTAGE_REASONS = ["Spoilage", "Breakage", "Expired", "Pest/Contamination",
                   "Over-cooked / Burnt", "Accident", "Other"]


class WastageIn(BaseModel):
    item_id:    str   = Field(min_length=1, max_length=100)
    date:       str   = Field(min_length=10, max_length=10)
    quantity:   float = Field(gt=0, le=100_000)
    reason:     str   = Field(min_length=1, max_length=200)
    notes:      Optional[str] = Field(default="", max_length=500)

    @field_validator("date")
    @classmethod
    def _vd(cls, v): return _validate_date(v)

    @field_validator("reason", "notes")
    @classmethod
    def _vs(cls, v): return _sanitize(v) if v else v


# ── Supplier ──────────────────────────────────────────────────────────────
class SupplierIn(BaseModel):
    name:      str = Field(min_length=1, max_length=200)
    phone:     Optional[str] = Field(default="", max_length=20)
    address:   Optional[str] = Field(default="", max_length=300)
    items:     Optional[str] = Field(
        default="", max_length=500,
        description="Comma-separated list of items this supplier provides")
    notes:     Optional[str] = Field(default="", max_length=500)

    @field_validator("name", "phone", "address", "items", "notes")
    @classmethod
    def _vs(cls, v): return _sanitize(v) if v else v


class SupplierUpdateIn(BaseModel):
    name:      Optional[str] = Field(default=None, max_length=200)
    phone:     Optional[str] = Field(default=None, max_length=20)
    address:   Optional[str] = Field(default=None, max_length=300)
    items:     Optional[str] = Field(default=None, max_length=500)
    notes:     Optional[str] = Field(default=None, max_length=500)
    is_active: Optional[bool] = None

    @field_validator("name", "phone", "address", "items", "notes")
    @classmethod
    def _vs(cls, v): return _sanitize(v) if v else v
