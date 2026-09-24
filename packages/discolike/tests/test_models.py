import pydantic
import pytest

from discolike._models import DiscolikeRequest
from discolike.requests import CountParams
from discolike.requests import DiscoverParams


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
    bbox: list[str] | None = None


class _GeoProbe(DiscolikeRequest):
    geo: list[str] | None = None


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
    assert _BboxProbe(bbox=value).to_wire() == {"bbox": [value]}


def test_bbox_accepts_several_boxes() -> None:
    boxes = ["40.4,-74.3,41.0,-73.7", "51.2,-0.5,51.7,0.3"]
    assert _BboxProbe(bbox=boxes).to_wire() == {"bbox": boxes}


def test_bbox_rejects_a_bad_box_among_good_ones() -> None:
    with pytest.raises(pydantic.ValidationError, match="latitudes must satisfy"):
        _BboxProbe(bbox=["40.4,-74.3,41.0,-73.7", "-91,0,10,1"])


@pytest.mark.parametrize(
    "value",
    [
        "30.27,-97.74",
        "30.27,-97.74,30mi",
        "30.27,-97.74,10km",
        "30.27,-97.74,10",
        "30.27, -97.74, 10 km",
        "-90,-180",
        "90,180,1000km",
    ],
)
def test_geo_accepts_valid_circles(value: str) -> None:
    assert _GeoProbe(geo=value).to_wire() == {"geo": [value]}


def test_geo_accepts_several_circles() -> None:
    circles = ["30.27,-97.74,10km", "52.52,13.405"]
    assert _GeoProbe(geo=circles).to_wire() == {"geo": circles}


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("30.27", "expected 2 or 3 values"),
        ("30.27,-97.74,10km,1", "expected 2 or 3 values"),
        ("north,-97.74", "must be numbers"),
        ("nan,-97.74", "must be finite"),
        ("90.5,-97.74", "latitude must be between"),
        ("30.27,-180.5", "longitude must be between"),
        ("30.27,-97.74,0km", "greater than 0"),
        ("30.27,-97.74,1001km", "greater than 0"),
        ("30.27,-97.74,wide", "must be a number optionally suffixed"),
    ],
)
def test_geo_rejects_circles_the_platform_would_reject(value: str, message: str) -> None:
    with pytest.raises(pydantic.ValidationError, match=message):
        _GeoProbe(geo=value)


def test_geo_none_stays_unvalidated() -> None:
    assert _GeoProbe(geo=None).to_wire() == {"geo": None}


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


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"lat": 40.0}, "lat and lon must be supplied together"),
        ({"lon": -74.0}, "lat and lon must be supplied together"),
        ({"radius": "10km"}, "radius needs lat and lon"),
        ({"lat": 40.0, "lon": -74.0, "radius": "wide"}, "must be a number optionally suffixed"),
        ({"lat": 40.0, "lon": -74.0, "radius": "1001km"}, "greater than 0"),
        ({"geo": ["30.27,-97.74"] * 11}, "11 geo shapes"),
        (
            {"lat": 40.0, "lon": -74.0, "geo": ["30.27,-97.74"] * 5, "bbox": ["40.4,-74.3,41.0,-73.7"] * 5},
            "11 geo shapes",
        ),
    ],
)
def test_discover_params_rejects_geo_combinations_the_platform_would_reject(
    kwargs: dict[str, object], message: str
) -> None:
    with pytest.raises(pydantic.ValidationError, match=message):
        DiscoverParams.model_validate(kwargs)


def test_discover_params_accepts_ten_shapes_and_a_centre_with_radius() -> None:
    DiscoverParams(lat=40.0, lon=-74.0, radius="30mi", geo=["30.27,-97.74"] * 4, bbox=["40.4,-74.3,41.0,-73.7"] * 5)


def test_count_params_rejects_lat_without_lon() -> None:
    with pytest.raises(pydantic.ValidationError, match="supplied together"):
        CountParams(lat=40.0)
