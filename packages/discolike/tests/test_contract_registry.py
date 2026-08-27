import importlib.util
import inspect
import pathlib
import sys

from discolike.resources._base import get_discolike_route

ALLOW_UNSTAMPED = {"job", "batch"}
SCRIPT_PATH = pathlib.Path(__file__).parents[3] / "scripts" / "check_contract.py"


def _load_check_contract():
    spec = importlib.util.spec_from_file_location("check_contract", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_all_public_resource_methods_are_stamped():
    check_contract = _load_check_contract()
    unstamped = []
    for module in check_contract._resource_modules():
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ != module.__name__:
                continue
            for name, member in vars(cls).items():
                if name.startswith("_") or name in ALLOW_UNSTAMPED:
                    continue
                if not inspect.isfunction(member):
                    continue
                if get_discolike_route(member) is None:
                    unstamped.append(f"{cls.__name__}.{name}")
    assert unstamped == []


def test_check_passes_against_minimal_matching_spec():
    check_contract = _load_check_contract()
    routes = [
        route
        for route in check_contract.collect_routes()
        if route.class_name == "AccountResource" and route.method_name == "usage"
    ]
    spec = {"paths": {"/usage": {"get": {"parameters": []}}}}
    assert check_contract.check(spec, routes) == []


def test_check_reports_missing_route_against_empty_spec():
    check_contract = _load_check_contract()
    routes = [
        route
        for route in check_contract.collect_routes()
        if route.class_name == "AccountResource" and route.method_name == "usage"
    ]
    mismatches = check_contract.check({"paths": {}}, routes)
    assert len(mismatches) == 1
    assert "/usage" in mismatches[0]


def test_check_models_passes_when_spec_matches_model():
    check_contract = _load_check_contract()
    from discolike.resources.companies import ExtractResult

    spec = {"components": {"schemas": {"ExtractResponse": {"properties": {"text": {}, "language": {}}}}}}
    assert check_contract.check_models(spec, {"ExtractResponse": ExtractResult}) == []


def test_check_models_reports_field_the_spec_does_not_have():
    check_contract = _load_check_contract()
    from discolike.resources.companies import ExtractResult

    spec = {"components": {"schemas": {"ExtractResponse": {"properties": {"text": {}}}}}}
    mismatches = check_contract.check_models(spec, {"ExtractResponse": ExtractResult})
    assert mismatches == ["ExtractResult: field 'language' not in spec schema 'ExtractResponse'"]


def test_check_models_reports_field_the_sdk_does_not_declare():
    check_contract = _load_check_contract()
    from discolike.resources.companies import ExtractResult

    spec = {"components": {"schemas": {"ExtractResponse": {"properties": {"text": {}, "language": {}, "summary": {}}}}}}
    mismatches = check_contract.check_models(spec, {"ExtractResponse": ExtractResult})
    assert mismatches == ["ExtractResult: spec schema 'ExtractResponse' has field 'summary' the SDK does not declare"]


def test_check_models_reports_missing_schema():
    check_contract = _load_check_contract()
    from discolike.resources.companies import ExtractResult

    mismatches = check_contract.check_models({"components": {"schemas": {}}}, {"ExtractResponse": ExtractResult})
    assert mismatches == ["ExtractResult: schema 'ExtractResponse' not found in spec"]


def test_mirrored_schemas_cover_the_shared_company_profile():
    check_contract = _load_check_contract()
    from discolike.resources.companies import CompanyProfile

    assert check_contract.MIRRORED_SCHEMAS["CompanyResult"] is CompanyProfile


def _route(check_contract, class_name: str, method_name: str):
    return [
        route
        for route in check_contract.collect_routes()
        if route.class_name == class_name and route.method_name == method_name
    ]


def _spec_with_params(path: str, names: list[str], *, deprecated: tuple[str, ...] = ()) -> dict:
    parameters: list[dict[str, object]] = [{"name": name, "in": "query"} for name in names]
    parameters.extend({"name": name, "in": "query", "deprecated": True} for name in deprecated)
    return {"paths": {path: {"get": {"parameters": parameters}}}}


def test_collect_routes_reads_the_request_model_from_the_annotation():
    check_contract = _load_check_contract()
    from discolike.requests import MatchCompanyParams

    (route,) = _route(check_contract, "MatchResource", "company")
    assert route.request_model is MatchCompanyParams


def test_collect_routes_leaves_request_model_none_for_bare_routes():
    check_contract = _load_check_contract()
    (route,) = _route(check_contract, "AccountResource", "usage")
    assert route.request_model is None


def test_check_passes_when_model_fields_match_spec_params():
    check_contract = _load_check_contract()
    from discolike.requests import MatchCompanyParams

    routes = _route(check_contract, "MatchResource", "company")
    spec = _spec_with_params("/match", list(MatchCompanyParams.model_fields), deprecated=("nl_match",))
    assert check_contract.check(spec, routes) == []


def test_check_reports_model_field_the_spec_lacks():
    check_contract = _load_check_contract()
    from discolike.requests import MatchCompanyParams

    routes = _route(check_contract, "MatchResource", "company")
    names = [name for name in MatchCompanyParams.model_fields if name != "zip_code"]
    mismatches = check_contract.check(_spec_with_params("/match", names), routes)
    assert mismatches == [
        "MatchResource.company (GET /match): field 'zip_code' of MatchCompanyParams not found in spec"
    ]


def test_check_reports_spec_param_the_model_lacks():
    check_contract = _load_check_contract()
    from discolike.requests import MatchCompanyParams

    routes = _route(check_contract, "MatchResource", "company")
    names = [*MatchCompanyParams.model_fields, "brand_new"]
    mismatches = check_contract.check(_spec_with_params("/match", names), routes)
    assert mismatches == [
        "MatchResource.company (GET /match): spec param 'brand_new' not declared on MatchCompanyParams"
    ]


def test_check_reports_params_on_a_route_without_a_model():
    check_contract = _load_check_contract()
    routes = _route(check_contract, "AccountResource", "usage")
    mismatches = check_contract.check(_spec_with_params("/usage", ["verbose"]), routes)
    assert mismatches == [
        "AccountResource.usage (GET /usage): spec has param 'verbose' but the method takes no request model"
    ]


def test_check_ignores_the_multipart_file_field():
    check_contract = _load_check_contract()
    from discolike.requests import MatchBulkParams

    routes = _route(check_contract, "MatchResource", "bulk")
    spec = {
        "paths": {
            "/bulkmatch": {
                "post": {
                    "parameters": [{"name": name, "in": "query"} for name in MatchBulkParams.model_fields],
                    "requestBody": {
                        "content": {"multipart/form-data": {"schema": {"$ref": "#/components/schemas/Body_bulk_match"}}}
                    },
                }
            }
        },
        "components": {"schemas": {"Body_bulk_match": {"properties": {"file": {"type": "string"}}}}},
    }
    assert check_contract.check(spec, routes) == []


def test_check_compares_json_body_properties_bidirectionally():
    check_contract = _load_check_contract()
    from discolike.requests import FindEmailRequest

    routes = _route(check_contract, "EmailResource", "find")
    properties = {name: {} for name in FindEmailRequest.model_fields}
    properties["legacy"] = {"deprecated": True}
    spec = {
        "paths": {
            "/email/find": {
                "post": {
                    "requestBody": {
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/FindEmailRequest"}}}
                    }
                }
            }
        },
        "components": {"schemas": {"FindEmailRequest": {"properties": properties}}},
    }
    assert check_contract.check(spec, routes) == []
