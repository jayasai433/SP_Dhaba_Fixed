from typing import List, Optional
from pydantic import BaseModel, Field

class ItemIn(BaseModel):
    name:          str
    category:      str
    unit:          str
    reorder_level: float = Field(ge=0)

class ItemUpdateIn(BaseModel):
    name:          Optional[str]   = None
    category:      Optional[str]   = None
    unit:          Optional[str]   = None
    reorder_level: Optional[float] = Field(default=None, ge=0)
    is_active:     Optional[bool]  = None

class BulkReorderItem(BaseModel):
    item_id:       str
    reorder_level: float

class BulkReorderIn(BaseModel):
    updates: List[BulkReorderItem]
