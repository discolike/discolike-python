import importlib
import importlib.util
import inspect
import pathlib
import pkgutil
import sys

import discolike.resources
from discolike.resources._base import get_discolike_route

ALLOW_UNSTAMPED = {"job"}
SCRIPT_PATH = pathlib.Path(__file__).parent.parent / "scripts" / "check_contract.py"


def _resource_modules():
    modules = [discolike.resources]
    modules.extend(
        importlib.import_module(module_info.name)
        for module_info in pkgutil.iter_modules(discolike.resources.__path__, prefix=f"{discolike.resources.__name__}.")
    )
    return modules


def _load_check_contract():
    spec = importlib.util.spec_from_file_location("check_contract", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_all_public_resource_methods_are_stamped():
    unstamped = []
    for module in _resource_modules():
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
