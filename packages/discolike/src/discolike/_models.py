from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import pydantic

BBOX_FIELD_COUNT = 4
BBOX_SEPARATOR = ","
BBOX_FORMAT = "min_lat,min_lon,max_lat,max_lon"
GEO_SEPARATOR = ","
GEO_FORMAT = "lat,lon or lat,lon,radius"
GEO_POINT_FIELD_COUNT = 2
GEO_CIRCLE_FIELD_COUNT = 3
MIN_LATITUDE = -90.0
MAX_LATITUDE = 90.0
MIN_LONGITUDE = -180.0
MAX_LONGITUDE = 180.0
MAX_RADIUS_KM = 1000.0
KM_PER_MILE = 1.609344
RADIUS_KM_SUFFIX = "km"
RADIUS_MILE_SUFFIX = "mi"
MAX_GEO_SHAPES = 10


class DiscolikeModel(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="allow")

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class DiscolikeRequest(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="allow", populate_by_name=True)

    # Mirrors the platform's parse_bbox and parse_geo_circle so a bad shape fails here instead of as
    # an opaque 4xx. The request models are generated, so the validators can only be attached from
    # the base class; check_fields=False keeps them inert on the models that have no geo or bbox.
    # A lone string is wrapped into a one-element list the way the platform coerces it.
    @pydantic.field_validator("bbox", mode="before", check_fields=False)
    @classmethod
    def _validate_bbox(cls, value: object) -> object:
        return _validate_shapes(value=value, name="bbox", fmt=BBOX_FORMAT, rejection=_bbox_rejection)

    @pydantic.field_validator("geo", mode="before", check_fields=False)
    @classmethod
    def _validate_geo(cls, value: object) -> object:
        return _validate_shapes(value=value, name="geo", fmt=GEO_FORMAT, rejection=_geo_rejection)

    @pydantic.model_validator(mode="after")
    def _validate_geo_shapes(self) -> DiscolikeRequest:
        if "lat" not in type(self).model_fields:
            return self
        lat, lon, radius = getattr(self, "lat", None), getattr(self, "lon", None), getattr(self, "radius", None)
        if (lat is None) != (lon is None):
            raise ValueError("lat and lon must be supplied together")
        if radius is not None:
            if lat is None:
                raise ValueError("radius needs lat and lon")
            reason = _radius_km_rejection(radius)
            if reason is not None:
                raise ValueError(reason)
        total = (lat is not None) + len(getattr(self, "geo", None) or []) + len(getattr(self, "bbox", None) or [])
        if total > MAX_GEO_SHAPES:
            raise ValueError(f"{total} geo shapes (lat/lon, geo and bbox together); at most {MAX_GEO_SHAPES}")
        return self

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


def _validate_shapes(
    *,
    value: object,
    name: str,
    fmt: str,
    rejection: Callable[[str], str | None],
) -> object:
    if value is None or not isinstance(value, str | list | tuple):
        return value
    shapes = [value] if isinstance(value, str) else list(value)
    for shape in shapes:
        if not isinstance(shape, str):
            return value
        reason = rejection(shape)
        if reason is not None:
            raise ValueError(f"invalid {name} {shape!r}: {reason}; use {fmt}")
    return shapes


def _radius_km_rejection(value: str) -> str | None:
    raw = value.strip().lower().replace(" ", "")
    multiplier = 1.0
    if raw.endswith(RADIUS_MILE_SUFFIX):
        raw, multiplier = raw[: -len(RADIUS_MILE_SUFFIX)], KM_PER_MILE
    elif raw.endswith(RADIUS_KM_SUFFIX):
        raw = raw[: -len(RADIUS_KM_SUFFIX)]
    try:
        radius_km = float(raw) * multiplier
    except ValueError:
        return f"radius {value!r} must be a number optionally suffixed with {RADIUS_KM_SUFFIX} or {RADIUS_MILE_SUFFIX}"
    if not math.isfinite(radius_km) or radius_km <= 0 or radius_km > MAX_RADIUS_KM:
        return f"radius {value!r} must be greater than 0 and at most {MAX_RADIUS_KM:g}km"
    return None


def _geo_rejection(value: str) -> str | None:
    parts = value.replace(" ", "").split(GEO_SEPARATOR)
    if not GEO_POINT_FIELD_COUNT <= len(parts) <= GEO_CIRCLE_FIELD_COUNT:
        return f"expected {GEO_POINT_FIELD_COUNT} or {GEO_CIRCLE_FIELD_COUNT} values, got {len(parts)}"
    try:
        lat, lon = float(parts[0]), float(parts[1])
    except ValueError:
        return "latitude and longitude must be numbers"
    if not (math.isfinite(lat) and math.isfinite(lon)):
        return "latitude and longitude must be finite"
    if not MIN_LATITUDE <= lat <= MAX_LATITUDE:
        return f"latitude must be between {MIN_LATITUDE} and {MAX_LATITUDE}"
    if not MIN_LONGITUDE <= lon <= MAX_LONGITUDE:
        return f"longitude must be between {MIN_LONGITUDE} and {MAX_LONGITUDE}"
    if len(parts) == GEO_CIRCLE_FIELD_COUNT:
        return _radius_km_rejection(parts[-1])
    return None
