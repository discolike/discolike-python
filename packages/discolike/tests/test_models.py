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
