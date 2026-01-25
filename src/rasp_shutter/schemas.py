#!/usr/bin/env python3
"""
Pydantic schemas for Web API.

These schemas are used for request validation and response serialization.
Internal data structures remain as dataclasses in types.py.
"""

from my_lib.pydantic import BaseSchema


# ======================================================================
# Request Schemas
# ======================================================================
class ShutterCtrlRequest(BaseSchema):
    """Shutter control request query parameters."""

    cmd: int = 0
    index: int = -1
    state: str = "close"


class ScheduleCtrlRequest(BaseSchema):
    """Schedule control request query parameters."""

    cmd: str | None = None
    data: str | None = None


class CtrlLogRequest(BaseSchema):
    """Control log request query parameters."""

    cmd: str = "get"


# ======================================================================
# Response Schemas
# ======================================================================
class SensorValueSchema(BaseSchema):
    """Sensor value response."""

    valid: bool
    value: float | None = None
    time: str | None = None


class SensorDataSchema(BaseSchema):
    """Sensor data response."""

    lux: SensorValueSchema
    solar_rad: SensorValueSchema
    altitude: SensorValueSchema


class ShutterStateEntrySchema(BaseSchema):
    """Shutter state entry response."""

    name: str
    state: int


class ShutterStateResponseSchema(BaseSchema):
    """Shutter state response."""

    state: list[ShutterStateEntrySchema]
    result: str = "success"
    cmd: str | None = None


class ScheduleEntrySchema(BaseSchema):
    """Schedule entry response."""

    is_active: bool
    time: str
    wday: list[bool]
    solar_rad: int
    lux: int
    altitude: int
    endpoint: str | None = None


class ScheduleDataSchema(BaseSchema):
    """Schedule data response."""

    open: ScheduleEntrySchema
    close: ScheduleEntrySchema


class CtrlLogResponseSchema(BaseSchema):
    """Control log response."""

    result: str
    log: list[dict] | None = None
