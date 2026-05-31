from typing import Optional
from pydantic import BaseModel, Field

class StaffIn(BaseModel):
    name:           str
    default_salary: float = Field(ge=0, default=0)
    phone:          Optional[str] = ""

class StaffUpdateIn(BaseModel):
    name:           Optional[str]   = None
    default_salary: Optional[float] = Field(default=None, ge=0)
    phone:          Optional[str]   = None
    is_active:      Optional[bool]  = None

class SalaryIn(BaseModel):
    staff_id:     str
    month:        str           # YYYY-MM
    basic_salary: float = Field(ge=0)
    advance_paid: float = Field(ge=0, default=0)
    notes:        Optional[str] = ""

class SalaryPayIn(BaseModel):
    paid_date: str              # YYYY-MM-DD
