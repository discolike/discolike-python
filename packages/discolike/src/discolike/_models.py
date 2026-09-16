from __future__ import annotations

from typing import Any

import pydantic

BBOX_PART_COUNT = 4
MAX_LATITUDE = 90.0
MAX_LONGITUDE = 180.0
BBOX_FORMAT = "min_lat,min_lon,max_lat,max_lon"


class DiscolikeModel(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="allow")

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class DiscolikeRequest(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="allow", populate_by_name=True)

    # The request models are generated, so a field validator can only be attached from the base
    # class; check_fields=False keeps it inert on the models that have no bbox.
    @pydantic.field_validator("bbox", check_fields=False)
    @classmethod
    def _validate_bbox(cls, value: str | None) -> str | None:
        if value is None:
            return value
        parts = value.split(",")
        if len(parts) != BBOX_PART_COUNT:
            raise ValueError(f"bbox must be {BBOX_FORMAT}, got {value!r}")
        try:
            min_lat, min_lon, max_lat, max_lon = (float(part) for part in parts)
        except ValueError:
            raise ValueError(f"bbox must be four numbers as {BBOX_FORMAT}, got {value!r}") from None
        for name, latitude in (("min_lat", min_lat), ("max_lat", max_lat)):
            if not -MAX_LATITUDE <= latitude <= MAX_LATITUDE:
                raise ValueError(f"bbox {name} must be between -{MAX_LATITUDE} and {MAX_LATITUDE}, got {latitude}")
        for name, longitude in (("min_lon", min_lon), ("max_lon", max_lon)):
            if not -MAX_LONGITUDE <= longitude <= MAX_LONGITUDE:
                raise ValueError(f"bbox {name} must be between -{MAX_LONGITUDE} and {MAX_LONGITUDE}, got {longitude}")
        if min_lat > max_lat:
            raise ValueError(f"bbox min_lat must not exceed max_lat, got {min_lat} and {max_lat}")
        return value

    def to_wire(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_unset=True, by_alias=True)
