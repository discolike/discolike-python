"""The generated request models must carry the sub-industry and geo filters."""

from discolike.requests import CountParams
from discolike.requests import DiscoverParams
from discolike.resources.companies import CompanyProfile

NEW_FILTERS = ("sub_industry", "negate_sub_industry", "lat", "lon", "radius")
NEW_OUTPUTS = ("sub_industry", "lat", "lon", "geo_precision")


class TestGeneratedRequests:
    def test_discover_params_carry_the_new_filters(self) -> None:
        assert set(NEW_FILTERS) <= set(DiscoverParams.model_fields)

    def test_count_params_carry_the_new_filters(self) -> None:
        assert set(NEW_FILTERS) <= set(CountParams.model_fields)


class TestCompanyProfile:
    def test_new_output_fields_exist(self) -> None:
        assert set(NEW_OUTPUTS) <= set(CompanyProfile.model_fields)

    def test_sub_industry_defaults_to_none_matching_the_platform_model(self) -> None:
        assert CompanyProfile(domain="acme.com").sub_industry is None

    def test_an_empty_mapping_is_preserved(self) -> None:
        assert CompanyProfile(domain="acme.com", sub_industry={}).sub_industry == {}
