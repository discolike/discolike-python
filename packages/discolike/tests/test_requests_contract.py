"""The generated request models must carry the sub-industry and geo filters."""

from discolike.requests import CountParams
from discolike.requests import DiscoverParams
from discolike.resources.companies import CompanyProfile

NEW_FILTERS = ("sub_industry", "negate_sub_industry", "lat", "lon", "radius", "geo", "bbox")
NEW_OUTPUTS = ("sub_industry", "latitude", "longitude", "geo_precision")


SUB_INDUSTRY = ["ROOFING", "CONSTRUCTION/ROOFING"]
NEGATE_SUB_INDUSTRY = ["FOUNDRIES"]
LAT = 40.7128
LON = -74.006
RADIUS = "30mi"
BBOX = "40.4,-74.3,41.0,-73.7"
BBOXES = ["40.4,-74.3,41.0,-73.7", "51.2,-0.5,51.7,0.3"]
GEO = ["30.27,-97.74,10km", "52.52,13.405"]


class TestGeneratedRequests:
    def test_discover_params_carry_the_new_filters(self) -> None:
        assert set(NEW_FILTERS) <= set(DiscoverParams.model_fields)

    def test_count_params_carry_the_new_filters(self) -> None:
        assert set(NEW_FILTERS) <= set(CountParams.model_fields)

    def test_discover_params_serialize_the_new_filters_onto_the_wire(self) -> None:
        wire = DiscoverParams(
            sub_industry=SUB_INDUSTRY,
            negate_sub_industry=NEGATE_SUB_INDUSTRY,
            lat=LAT,
            lon=LON,
            radius=RADIUS,
        ).to_wire()
        assert wire["sub_industry"] == ["ROOFING", "CONSTRUCTION/ROOFING"]
        assert wire["negate_sub_industry"] == ["FOUNDRIES"]
        assert wire["lat"] == 40.7128
        assert wire["lon"] == -74.006
        assert wire["radius"] == "30mi"
        assert isinstance(wire["sub_industry"], list)
        assert isinstance(wire["lat"], float)
        assert isinstance(wire["lon"], float)
        assert isinstance(wire["radius"], str)

    def test_count_params_serialize_the_new_filters_onto_the_wire(self) -> None:
        wire = CountParams(
            sub_industry=SUB_INDUSTRY,
            negate_sub_industry=NEGATE_SUB_INDUSTRY,
            lat=LAT,
            lon=LON,
            radius=RADIUS,
        ).to_wire()
        assert wire["sub_industry"] == ["ROOFING", "CONSTRUCTION/ROOFING"]
        assert wire["negate_sub_industry"] == ["FOUNDRIES"]
        assert wire["lat"] == 40.7128
        assert wire["lon"] == -74.006
        assert wire["radius"] == "30mi"

    def test_discover_params_serialize_bbox_onto_the_wire(self) -> None:
        assert DiscoverParams(bbox=BBOX).to_wire()["bbox"] == [BBOX]

    def test_count_params_serialize_bbox_onto_the_wire(self) -> None:
        assert CountParams(bbox=BBOX).to_wire()["bbox"] == [BBOX]

    def test_discover_params_serialize_several_boxes_onto_the_wire(self) -> None:
        assert DiscoverParams(bbox=BBOXES).to_wire()["bbox"] == BBOXES

    def test_count_params_serialize_several_boxes_onto_the_wire(self) -> None:
        assert CountParams(bbox=BBOXES).to_wire()["bbox"] == BBOXES

    def test_discover_params_serialize_geo_onto_the_wire(self) -> None:
        assert DiscoverParams(geo=GEO).to_wire()["geo"] == GEO

    def test_count_params_serialize_geo_onto_the_wire(self) -> None:
        assert CountParams(geo=GEO).to_wire()["geo"] == GEO

    def test_a_single_geo_circle_may_be_a_bare_string(self) -> None:
        assert DiscoverParams(geo="30.27,-97.74").to_wire()["geo"] == ["30.27,-97.74"]

    def test_geo_and_bbox_and_a_lat_lon_centre_combine(self) -> None:
        wire = DiscoverParams(geo=GEO, bbox=BBOXES, lat=LAT, lon=LON, radius=RADIUS).to_wire()
        assert wire["geo"] == GEO
        assert wire["bbox"] == BBOXES
        assert wire["lat"] == LAT

    def test_unset_new_filters_are_dropped_by_exclude_unset(self) -> None:
        wire = DiscoverParams(icp_prompt="widgets").to_wire()
        for field in NEW_FILTERS:
            assert field not in wire

    def test_sub_industry_accepts_a_bare_label(self) -> None:
        request = DiscoverParams(sub_industry=["ROOFING"])
        assert request.to_wire()["sub_industry"] == ["ROOFING"]

    def test_sub_industry_accepts_a_parent_qualified_key(self) -> None:
        request = DiscoverParams(sub_industry=["CONSTRUCTION/ROOFING"])
        assert request.to_wire()["sub_industry"] == ["CONSTRUCTION/ROOFING"]


class TestCompanyProfile:
    def test_new_output_fields_exist(self) -> None:
        assert set(NEW_OUTPUTS) <= set(CompanyProfile.model_fields)

    def test_sub_industry_defaults_to_none_matching_the_platform_model(self) -> None:
        assert CompanyProfile(domain="acme.com").sub_industry is None

    def test_an_empty_mapping_is_preserved(self) -> None:
        assert CompanyProfile(domain="acme.com", sub_industry={}).sub_industry == {}

    def test_a_populated_response_parses_the_new_fields(self) -> None:
        profile = CompanyProfile.model_validate(
            {
                "domain": "acme.com",
                "sub_industry": {"ROOFING": 0.92, "FOUNDRIES": 0.11},
                "latitude": 40.7128,
                "longitude": -74.006,
                "geo_precision": "city",
            }
        )
        assert profile.sub_industry == {"ROOFING": 0.92, "FOUNDRIES": 0.11}
        assert isinstance(profile.latitude, float)
        assert isinstance(profile.longitude, float)
        assert profile.latitude == 40.7128
        assert profile.longitude == -74.006
        assert profile.geo_precision == "city"

    def test_the_pre_rename_coordinate_keys_still_parse(self) -> None:
        profile = CompanyProfile.model_validate({"domain": "acme.com", "lat": 40.7128, "lon": -74.006})

        assert profile.latitude == 40.7128
        assert profile.longitude == -74.006

    def test_coordinates_serialize_under_their_full_names(self) -> None:
        profile = CompanyProfile.model_validate({"domain": "acme.com", "lat": 40.7128, "lon": -74.006})

        assert profile.to_dict()["latitude"] == 40.7128
        assert profile.to_dict()["longitude"] == -74.006
