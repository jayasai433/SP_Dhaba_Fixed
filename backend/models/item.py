from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
import re as _re


def _sanitize(v: str) -> str:
    """Strip HTML/script tags so item names cannot be used for stored XSS."""
    v = _re.sub(r"<[^>]+>", "", v)
    v = _re.sub(r"javascript:", "", v, flags=_re.IGNORECASE)
    return v.strip()


class UnitEntry(BaseModel):
    """
    One valid unit for an item plus the conversion factor to the item's base unit.

    Example for eggs (base_unit=piece):
        {"name": "piece", "conversion_factor": 1,  "is_default": True}
        {"name": "dozen", "conversion_factor": 12, "is_default": False}
        {"name": "tray",  "conversion_factor": 30, "is_default": False}

    conversion_factor = how many base_units are in one of this unit.
    Purchases store both `quantity` (in the chosen unit) and `base_quantity`
    (quantity multiplied by conversion_factor), so a future stock module can
    aggregate purely on `base_quantity` without unit gymnastics.
    """
    name: str = Field(min_length=1, max_length=50)
    conversion_factor: float = Field(gt=0, le=100_000)
    is_default: bool = False

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v):
        return _sanitize(v)


class ItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: Optional[str] = Field(default="", max_length=100)
    base_unit: str = Field(min_length=1, max_length=50,
                           description="The canonical unit used for stock aggregation, e.g. piece, kg, L.")
    default_price: Optional[float] = Field(default=0, ge=0, le=999_999.99)
    units: List[UnitEntry] = Field(
        default_factory=list,
        description="All valid units for this item. Must include base_unit with conversion_factor 1.",
    )

    @field_validator("name", "category", "base_unit")
    @classmethod
    def sanitize(cls, v):
        return _sanitize(v) if v else v

    @model_validator(mode="after")
    def ensure_base_unit_present(self):
        names = [u.name.lower() for u in self.units]
        base = self.base_unit.lower()
        if not self.units:
            # If no explicit units, create a single-unit list matching base_unit
            self.units = [UnitEntry(name=self.base_unit, conversion_factor=1.0, is_default=True)]
        elif base not in names:
            self.units.append(UnitEntry(name=self.base_unit, conversion_factor=1.0, is_default=True))
        # Guarantee exactly one default
        has_default = any(u.is_default for u in self.units)
        if not has_default:
            for u in self.units:
                if u.name.lower() == base:
                    u.is_default = True
                    break
            else:
                self.units[0].is_default = True
        return self


class ItemUpdateIn(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    category: Optional[str] = Field(default=None, max_length=100)
    base_unit: Optional[str] = Field(default=None, max_length=50)
    default_price: Optional[float] = Field(default=None, ge=0, le=999_999.99)
    units: Optional[List[UnitEntry]] = None
    is_active: Optional[bool] = None

    @field_validator("name", "category", "base_unit")
    @classmethod
    def sanitize(cls, v):
        return _sanitize(v) if v else v
