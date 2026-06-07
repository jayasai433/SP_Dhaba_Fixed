"""
Closing Stock models.

Designed for extensibility:
  - ClosingStockIn     : what Lokesh submits (physical shelf count)
  - ClosingStockOut    : what API returns (computed fields added)
  - DailyStockSummary  : aggregate for dashboard/reports

Future: WastageIn (dish-level wastage), ForecastOut (predicted usage)
"""

import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator


def _validate_date(v: str) -> str:
    """
    Enforce YYYY-MM-DD, reject future dates.
    Uses IST (Asia/Kolkata) for today — between 12am-5:30am IST
    the UTC date is still the previous day, causing false rejections.
    """
    from datetime import date, datetime
    import pytz
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        raise ValueError("Date must be YYYY-MM-DD format")
    today_ist = datetime.now(pytz.timezone("Asia/Kolkata")).date()
    if date.fromisoformat(v) > today_ist:
        raise ValueError("Future dates not allowed")
    return v


class ClosingStockIn(BaseModel):
    """
    Physical shelf count submitted by staff at end of day.
    One entry per item per date.
    """
    date:          str   = Field(min_length=10, max_length=10,
                                  description="Date of physical count YYYY-MM-DD")
    item_id:       str   = Field(min_length=1, max_length=100)
    closing_qty:   float = Field(ge=0, le=100_000,
                                  description="Physical quantity remaining on shelf")
    notes:         Optional[str] = Field(default="", max_length=500)

    @field_validator("date")
    @classmethod
    def validate_date(cls, v): return _validate_date(v)

    @field_validator("item_id")
    @classmethod
    def validate_item_id(cls, v):
        if not re.fullmatch(r"[a-zA-Z0-9_\-]{1,100}", v):
            raise ValueError("Invalid item ID")
        return v


class ClosingStockOut(BaseModel):
    """
    Full computed record returned by API.
    All computed fields are read-only — never set by client.
    """
    id:               str
    date:             str
    item_id:          str
    item_name:        str
    unit:             str

    # Physical count (entered by Lokesh)
    closing_qty:      float

    # Computed fields (server-side only)
    opening_qty:      float   # previous day closing (or 0 if first entry)
    purchased_today:  float   # sum of purchases for this item on this date
    consumed:         float   # opening + purchased - closing (actual consumption)
    manual_usage:     float   # from usage collection (for cross-check)
    variance:         float   # consumed - manual_usage (positive = more used than recorded)
    variance_pct:     float   # variance / consumed * 100
    wastage_flag:     bool    # True if variance_pct > threshold (default 10%)

    notes:            Optional[str] = ""
    recorded_by:      str
    recorded_at:      str


class DailyStockSummary(BaseModel):
    """
    Aggregate summary for a given date — used in dashboard/reports.
    Extensible: add wastage_cost, forecast_accuracy etc. in future.
    """
    date:             str
    total_items:      int
    items_counted:    int     # how many items have closing stock for this date
    total_consumed:   float
    total_variance:   float
    high_variance_items: list  # items with wastage_flag=True
    wastage_cost_est: float   # estimated ₹ wastage (consumed * price)
