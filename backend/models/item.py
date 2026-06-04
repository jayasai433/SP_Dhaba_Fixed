from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
import re as _re

def _sanitize(v: str) -> str:
    """Strip HTML/script tags — prevent stored XSS via item names."""
    v = _re.sub(r"<[^>]+>", "", v)
    v = _re.sub(r"javascript:", "", v, flags=_re.IGNORECASE)
    return v.strip()

class ItemIn(BaseModel):
    name:          str = Field(min_length=1, max_length=200)
    category:      str = Field(min_length=1, max_length=100)
    unit:          str = Field(min_length=1, max_length=50)
    reorder_level: float = Field(ge=0, le=100_000)

    @field_validator("name", "category", "unit")
    @classmethod
    def sanitize(cls, v): return _sanitize(v)

class ItemUpdateIn(BaseModel):
    name:          Optional[str]   = Field(default=None, max_length=200)
    category:      Optional[str]   = Field(default=None, max_length=100)
    unit:          Optional[str]   = Field(default=None, max_length=50)
    reorder_level: Optional[float] = Field(default=None, ge=0, le=100_000)
    is_active:     Optional[bool]  = None

    @field_validator("name", "category", "unit")
    @classmethod
    def sanitize(cls, v): return _sanitize(v) if v else v

class BulkReorderItem(BaseModel):
    item_id:       str
    reorder_level: float

class BulkReorderIn(BaseModel):
    updates: List[BulkReorderItem]
