from __future__ import annotations
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    ForeignKey,
    Date,
    Boolean,
    Numeric,
    Enum as SAEnum,
    Index,
)
from sqlalchemy.orm import relationship

from .db import Base

class RateType(str, Enum):
    PERCENT = "percent"
    PER_KG = "per_kg"
    PER_ITEM = "per_item"

class HTC(Base):
    __tablename__ = "htc"

    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)

    rates = relationship("Rate", back_populates="htc", cascade="all, delete-orphan")

class Rate(Base):
    __tablename__ = "rate"

    id = Column(Integer, primary_key=True)
    htc_id = Column(Integer, ForeignKey("htc.id"), nullable=False, index=True)

    country_iso = Column(String(2), nullable=False, index=True)
    rate_type = Column(SAEnum(RateType), nullable=False)
    value = Column(Numeric(18, 6), nullable=False)  # Decimal

    currency = Column(String(3), nullable=True)  # ex: NOK for per_kg/per_item
    unit = Column(String(16), nullable=True)  # ex: kg, item

    is_exemption = Column(Boolean, nullable=False, default=False)
    agreement = Column(String(128), nullable=True)
    conditions = Column(Text, nullable=True)

    valid_from = Column(Date, nullable=True)
    valid_to = Column(Date, nullable=True)

    source_url = Column(Text, nullable=True)
    priority = Column(Integer, nullable=True)

    htc = relationship("HTC", back_populates="rates")

Index("ix_rate_htc_country", Rate.htc_id, Rate.country_iso)
