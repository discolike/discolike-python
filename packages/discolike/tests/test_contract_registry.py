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
