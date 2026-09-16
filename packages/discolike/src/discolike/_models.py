from __future__ import annotations

import math
from typing import Any

import pydantic

BBOX_FIELD_COUNT = 4
BBOX_SEPARATOR = ","
BBOX_FORMAT = "min_lat,min_lon,max_lat,max_lon"
MIN_LATITUDE = -90.0
MAX_LATITUDE = 90.0
MIN_LONGITUDE = -180.0
MAX_LONGITUDE = 180.0


class DiscolikeModel(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="allow")

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class DiscolikeRequest(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="allow", populate_by_name=True)

    # Mirrors the platform's parse_bbox so a bad box fails here instead of as an opaque 4xx. The
    # request models are generated, so the validator can only be attached from the base class;
    # check_fields=False keeps it inert on the models that have no bbox.
    @pydantic.field_validator("bbox", check_fields=False)
    @classmethod
    def _validate_bbox(cls, value: str | None) -> str | None:
        if value is None:
            return value
        reason = _bbox_rejection(value)
        if reason is not None:
            raise ValueError(f"invalid bbox {value!r}: {reason}; use {BBOX_FORMAT}")
        return value

    def to_wire(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_unset=True, by_alias=True)


def _bbox_rejection(value: str) -> str | None:
    parts = value.replace(" ", "").split(BBOX_SEPARATOR)
    if len(parts) != BBOX_FIELD_COUNT:
        return f"expected {BBOX_FIELD_COUNT} values, got {len(parts)}"
    try:
        min_lat, min_lon, max_lat, max_lon = (float(part) for part in parts)
    except ValueError:
        return "every value must be a number"
    if not all(math.isfinite(corner) for corner in (min_lat, min_lon, max_lat, max_lon)):
        return "every value must be finite"
    if not MIN_LATITUDE <= min_lat < max_lat <= MAX_LATITUDE:
        return f"latitudes must satisfy {MIN_LATITUDE} <= min_lat < max_lat <= {MAX_LATITUDE}"
    if not (MIN_LONGITUDE <= min_lon <= MAX_LONGITUDE and MIN_LONGITUDE <= max_lon <= MAX_LONGITUDE):
        return f"longitudes must be between {MIN_LONGITUDE} and {MAX_LONGITUDE}"
    if min_lon == max_lon:
        return "min_lon and max_lon must differ"
    return None
