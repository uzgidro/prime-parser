"""Domain models for hydropower plant data."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class StationData(BaseModel):
    """Data for a single hydropower station (for future use)."""

    name: str = Field(..., description="Station name")
    installed_capacity_mw: Optional[Decimal] = Field(
        None, description="Installed capacity in MW"
    )
    daily_energy_million_kwh: Optional[Decimal] = Field(
        None, description="Daily energy production in million kWh"
    )
    water_level: Optional[Decimal] = Field(None, description="Water level")
    water_volume_million_m3: Optional[Decimal] = Field(
        None, description="Water volume in million m³"
    )
    power_mw: Optional[Decimal] = Field(None, description="Current power in MW")
    aggregates_total: Optional[int] = Field(None, description="Total number of aggregates")
    aggregates_working: Optional[int] = Field(
        None, description="Number of working aggregates"
    )
    temperature: Optional[str] = Field(None, description="Temperature")


class HydropowerReport(BaseModel):
    """Complete hydropower report."""

    report_date: date = Field(..., description="Report date")
    total_daily_energy_million_kwh: Decimal = Field(
        ..., description="Total daily energy production for Uzbekgidroenergo"
    )
    stations: list[StationData] = Field(
        default_factory=list, description="All station data"
    )


class ParsedData(BaseModel):
    """Parsed data for API response (current version - only date and total energy)."""

    report_date: date = Field(..., description="Report date", alias="date")
    total_energy_production: Decimal = Field(
        ..., description="Total daily energy production in million kWh"
    )

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "date": "2026-01-08",
                "total_energy_production": 81.03
            }
        }
    )
