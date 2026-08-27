from __future__ import annotations

from typing import Any

import pydantic


class DiscolikeModel(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="allow")

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class DiscolikeRequest(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="allow", populate_by_name=True)

    def to_wire(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_unset=True, by_alias=True)
