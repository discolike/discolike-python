import pydantic
import pytest

from discolike._models import DiscolikeRequest


class _Probe(DiscolikeRequest):
    name: str
    city: str | None = None
    limit: int = 10
    zip_code: str | None = pydantic.Field(default=None, alias="zip")


def test_to_wire_sends_only_fields_that_were_set() -> None:
    assert _Probe(name="Acme").to_wire() == {"name": "Acme"}


def test_to_wire_keeps_an_explicit_none() -> None:
    assert _Probe(name="Acme", city=None).to_wire() == {"name": "Acme", "city": None}


def test_to_wire_passes_unknown_fields_through() -> None:
    assert _Probe.model_validate({"name": "Acme", "bogus": 1}).to_wire() == {"name": "Acme", "bogus": 1}


def test_populate_by_name_accepts_the_field_name_and_dumps_the_alias() -> None:
    assert _Probe(name="Acme", zip_code="78701").to_wire() == {"name": "Acme", "zip": "78701"}


def test_missing_required_field_raises_validation_error() -> None:
    with pytest.raises(pydantic.ValidationError):
        _Probe.model_validate({})


def test_discolike_request_is_exported_from_the_package() -> None:
    import discolike

    assert discolike.DiscolikeRequest is DiscolikeRequest


class _BboxProbe(DiscolikeRequest):
    bbox: str | None = None


@pytest.mark.parametrize(
    "value",
    [
        "40.4,-74.3,41.0,-73.7",
        "-90,-180,90,180",
        "-10,170,10,-170",
        "40.4, -74.3, 41.0, -73.7",
    ],
)
def test_bbox_accepts_valid_boxes(value: str) -> None:
    assert _BboxProbe(bbox=value).to_wire() == {"bbox": value}


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("40.4,-74.3,41.0", "expected 4 values"),
        ("40.4,-74.3,41.0,-73.7,1", "expected 4 values"),
        ("40.4,-74.3,41.0,east", "must be a number"),
        ("nan,-74.3,41.0,-73.7", "must be finite"),
        ("-inf,-74.3,41.0,-73.7", "must be finite"),
        ("-91,0,10,1", "latitudes must satisfy"),
        ("0,0,90.5,1", "latitudes must satisfy"),
        ("41,-74,40,-73", "latitudes must satisfy"),
        ("0,0,0,1", "latitudes must satisfy"),
        ("0,-180.5,10,1", "longitudes must be between"),
        ("0,0,10,180.5", "longitudes must be between"),
        ("0,10,1,10", "min_lon and max_lon must differ"),
    ],
)
def test_bbox_rejects_boxes_the_platform_would_reject(value: str, message: str) -> None:
    with pytest.raises(pydantic.ValidationError, match=message):
        _BboxProbe(bbox=value)


def test_bbox_none_stays_unvalidated() -> None:
    assert _BboxProbe(bbox=None).to_wire() == {"bbox": None}
