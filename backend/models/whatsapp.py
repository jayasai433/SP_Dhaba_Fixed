from typing import Optional
from pydantic import BaseModel, Field

class WhatsAppNumberIn(BaseModel):
    name:      str
    phone:     str           # E.164 without +, e.g. 919876543210
    is_active: bool = True

class WhatsAppNumberUpdateIn(BaseModel):
    name:      Optional[str]  = None
    phone:     Optional[str]  = None
    is_active: Optional[bool] = None

class WhatsAppSettingsIn(BaseModel):
    notify_out_of_stock:       Optional[bool]  = None
    notify_low_stock:          Optional[bool]  = None
    notify_large_purchase:     Optional[bool]  = None
    large_purchase_threshold:  Optional[float] = Field(default=None, ge=0)
    notify_morning_report:     Optional[bool]  = None
    notify_daily_report:       Optional[bool]  = None
    notify_no_sales_reminder:  Optional[bool]  = None
    notify_daily_loss:         Optional[bool]  = None

class WhatsAppTestIn(BaseModel):
    number_id: str
