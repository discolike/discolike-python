from __future__ import annotations

import argparse
import importlib
import inspect
import json
import pathlib
import pkgutil
import sys
from dataclasses import dataclass
from types import ModuleType

import httpx2

import discolike.resources
from discolike._models import DiscolikeModel
from discolike.resources._base import get_discolike_route
from discolike.resources.companies import CompanyProfile
from discolike.resources.companies import ExtractResult
from discolike.resources.companies import Growth
from discolike.resources.companies import PublicLink
from discolike.resources.companies import Redirect
from discolike.resources.companies import Score
from discolike.resources.companies import Subsidiary
from discolike.resources.companies import Vendor
from discolike.resources.match import MatchResponse
from discolike.resources.queries import SavedQueries

IGNORE_PARAMS = {"file", "contacts", "domain_column"}

# SDK response model -> the OpenAPI component schema it mirrors. Anything listed here is
# checked field-by-field against the spec, so a platform-side model change surfaces as a
# contract failure instead of silently landing in `extra`.
MIRRORED_SCHEMAS: dict[str, type[DiscolikeModel]] = {
    "CompanyResult": CompanyProfile,
    "ExtractResponse": ExtractResult,
    "ScoreResponse": Score,
    "GrowthResponse": Growth,
    "RedirectResult": Redirect,
    "VendorResult": Vendor,
    "SubsidiaryResult": Subsidiary,
    "PublicLinkResult": PublicLink,
    "MatchResponse": MatchResponse,
    "SavedQueriesListResponse": SavedQueries,
}
SPEC_URL = "https://api.discolike.com/v1/openapi.json"
REQUEST_TIMEOUT_SECONDS = 30.0
PATH_METHODS_WITH_BODY = {"POST", "PUT", "PATCH"}


@dataclass(frozen=True)
class RouteEntry:
    class_name: str
    method_name: str
    http_method: str
    path: str
    openapi: bool
    params: tuple[str, ...]


def _resource_modules() -> list[ModuleType]:
    modules = [discolike.resources]
    modules.extend(
        importlib.import_module(module_info.name)
        for module_info in pkgutil.walk_packages(
            discolike.resources.__path__, prefix=f"{discolike.resources.__name__}."
        )
    )
    return modules


def collect_routes() -> list[RouteEntry]:
    seen: dict[tuple[str, str], RouteEntry] = {}
    for module in _resource_modules():
        for class_name, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ != module.__name__:
                continue
            for method_name, member in vars(cls).items():
                if not inspect.isfunction(member):
                    continue
                route = get_discolike_route(member)
                if route is None:
                    continue
                http_method, path, openapi = route
                key = (http_method, path)
                if key in seen:
                    continue
                excluded = IGNORE_PARAMS
                params = tuple(
                    name
                    for name, param in inspect.signature(member).parameters.items()
                    if param.kind is inspect.Parameter.KEYWORD_ONLY and name not in excluded
                )
                seen[key] = RouteEntry(class_name, method_name, http_method, path, openapi, params)
    return list(seen.values())


def _resolve_ref(*, spec: dict, schema: dict) -> dict:
    ref = schema.get("$ref")
    if ref is None:
        return schema
    node = spec
    for part in ref.lstrip("#/").split("/"):
        node = node[part]
    return node


def _request_body_properties(*, spec: dict, operation: dict) -> set[str]:
    content = operation.get("requestBody", {}).get("content", {})
    for media_type in content.values():
        schema = _resolve_ref(spec=spec, schema=media_type.get("schema", {}))
        return set(schema.get("properties", {}).keys())
    return set()


def check(spec: dict, routes: list[RouteEntry]) -> list[str]:
    mismatches: list[str] = []
    paths = spec.get("paths", {})
    for route in routes:
        if not route.openapi:
            continue
        label = f"{route.class_name}.{route.method_name} ({route.http_method} {route.path})"
        path_item = paths.get(route.path)
        operation = path_item.get(route.http_method.lower()) if path_item is not None else None
        if operation is None:
            mismatches.append(f"{label}: route not found in spec")
            continue
        allowed = {p["name"] for p in operation.get("parameters", [])}
        if route.http_method.upper() in PATH_METHODS_WITH_BODY:
            allowed |= _request_body_properties(spec=spec, operation=operation)
        mismatches.extend(
            f"{label}: param '{param}' not found in spec" for param in route.params if param not in allowed
        )
    return mismatches


def check_models(spec: dict, mirrored: dict[str, type[DiscolikeModel]] | None = None) -> list[str]:
    mismatches: list[str] = []
    schemas = spec.get("components", {}).get("schemas", {})
    for schema_name, model in (MIRRORED_SCHEMAS if mirrored is None else mirrored).items():
        schema = schemas.get(schema_name)
        if schema is None:
            mismatches.append(f"{model.__name__}: schema '{schema_name}' not found in spec")
            continue
        spec_fields = set(schema.get("properties", {}).keys())
        model_fields = set(model.model_fields)
        mismatches.extend(
            f"{model.__name__}: field '{field}' not in spec schema '{schema_name}'"
            for field in sorted(model_fields - spec_fields)
        )
        mismatches.extend(
            f"{model.__name__}: spec schema '{schema_name}' has field '{field}' the SDK does not declare"
            for field in sorted(spec_fields - model_fields)
        )
    return mismatches


def load_spec(*, spec_path: str | None, spec_url: str) -> dict:
    if spec_path is not None:
        return json.loads(pathlib.Path(spec_path).read_text())
    response = httpx2.get(spec_url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the discolike SDK surface against the live OpenAPI spec.")
    parser.add_argument("--spec", default=None, help="Path to a local OpenAPI spec JSON file (offline mode).")
    parser.add_argument("--spec-url", default=SPEC_URL, help="OpenAPI spec URL (defaults to the production spec).")
    args = parser.parse_args()

    spec = load_spec(spec_path=args.spec, spec_url=args.spec_url)
    routes = collect_routes()
    checked = [route for route in routes if route.openapi]
    skipped = [route for route in routes if not route.openapi]

    for route in sorted(skipped, key=lambda r: r.path):
        print(f"skipped (not in public schema): {route.http_method} {route.path}")

    mismatches = check(spec, routes) + check_models(spec)

    print(f"checked {len(checked)} routes, skipped {len(skipped)} routes, {len(MIRRORED_SCHEMAS)} response models")

    if mismatches:
        print("MISMATCHES:")
        for mismatch in mismatches:
            print(f"  {mismatch}")
        return 1

    print("all routes and response models match the spec")
    return 0


if __name__ == "__main__":
    sys.exit(main())
