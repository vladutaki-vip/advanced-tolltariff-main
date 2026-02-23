from __future__ import annotations
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field

class RateType(str, Enum):
    percent = "percent"
    per_kg = "per_kg"
    per_item = "per_item"

class Rate(BaseModel):
    # Allow '*' wildcard or groups (e.g., 'EU'), so 1-3 chars
    country_iso: str = Field(min_length=1, max_length=3)
    rate_type: RateType
    value: Decimal
    currency: Optional[str] = None
    unit: Optional[str] = None
    is_exemption: bool = False
    agreement: Optional[str] = None
    agreement_name: Optional[str] = None
    conditions: Optional[str] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None

class HTC(BaseModel):
    code: str
    name: Optional[str] = None
    description: Optional[str] = None
    rates: List[Rate] = Field(default_factory=list)

class HTCResponse(BaseModel):
    htc: HTC

class HTCSummary(BaseModel):
    code: str
    name: Optional[str] = None
    description: Optional[str] = None
