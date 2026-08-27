import pydantic
import pytest

import discolike.requests as requests_module
from discolike._models import DiscolikeRequest
from discolike.requests import DiscoverParams
from discolike.requests import LLMProviderUpdateRequest
from discolike.requests import MatchCompanyParams


def test_every_exported_name_is_a_request_model() -> None:
    for name in requests_module.__all__:
        assert issubclass(getattr(requests_module, name), DiscolikeRequest), name


def test_all_is_sorted_and_complete() -> None:
    public = sorted(
        name
        for name, value in vars(requests_module).items()
        if isinstance(value, type) and issubclass(value, DiscolikeRequest)
    )
    assert list(requests_module.__all__) == public


def test_constraint_violations_fail_before_any_request() -> None:
    with pytest.raises(pydantic.ValidationError, match="min_similarity"):
        DiscoverParams(min_similarity=200)
    with pytest.raises(pydantic.ValidationError, match="name"):
        MatchCompanyParams.model_validate({})


def test_required_nullable_field_survives_generation() -> None:
    request = LLMProviderUpdateRequest(integration_name="n", provider="p", model_name="m", api_key=None)
    assert request.to_wire()["api_key"] is None
    with pytest.raises(pydantic.ValidationError, match="api_key"):
        LLMProviderUpdateRequest.model_validate({"integration_name": "n", "provider": "p", "model_name": "m"})


def test_models_allow_extra_fields() -> None:
    assert MatchCompanyParams.model_validate({"name": "Acme", "future_flag": 1}).to_wire()["future_flag"] == 1
