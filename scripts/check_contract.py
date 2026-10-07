from __future__ import annotations

import argparse
import importlib
import inspect
import json
import pathlib
import pkgutil
import sys
import typing
from dataclasses import dataclass
from types import ModuleType
from typing import Any
from typing import Literal

import httpx2

import discolike.resources
from discolike._models import DiscolikeModel
from discolike._models import DiscolikeRequest
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
from discolike.resources.prospecting import ProspectingEvent
from discolike.resources.prospecting import ProspectingInFlight
from discolike.resources.prospecting import ProspectingMessage
from discolike.resources.prospecting import ProspectingPlan
from discolike.resources.prospecting import ProspectingRun
from discolike.resources.prospecting import ProspectingRunSummary
from discolike.resources.queries import SavedQueries

IGNORE_PARAMS = {"file"}
QUERY_LOCATION = "query"
ASYNC_CLASS_PREFIX = "Async"

# SDK response model -> the OpenAPI component schema it mirrors. Anything listed here is
# checked field-by-field against the spec, so a platform-side model change surfaces as a
# contract failure instead of silently landing in `extra`.
MIRRORED_SCHEMAS: dict[str, type[DiscolikeModel]] = {
    "ProspectingRunResponse": ProspectingRun,
    "ProspectingPlan": ProspectingPlan,
    "ProspectingEvent": ProspectingEvent,
    "ProspectingMessage": ProspectingMessage,
    "ProspectingInFlight": ProspectingInFlight,
    "ProspectingRunSummary": ProspectingRunSummary,
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
# Request fields the platform accepts but hides from its OpenAPI schema (SkipJsonSchema), so the spec never lists them.
HIDDEN_REQUEST_FIELDS: dict[str, frozenset[str]] = {"ProspectingBrief": frozenset({"checkpoints"})}
# Methods that build a route's body from their own arguments instead of taking its request model, mapped
# argument -> body field, so each argument is checked against the body field it fills.
BODY_BUILDERS: dict[tuple[str, str], dict[str, str]] = {
    ("ProspectingResource", "answer_intake"): {"answers": "intake", "summary": "text"},
}
SPEC_URL = "https://api.discolike.com/v1/openapi.json"
REQUEST_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class RouteEntry:
    class_name: str
    method_name: str
    http_method: str
    path: str
    openapi: bool
    request_model: type[DiscolikeRequest] | None
    body_arguments: dict[str, Any]


def _resource_modules() -> list[ModuleType]:
    modules = [discolike.resources]
    modules.extend(
        importlib.import_module(module_info.name)
        for module_info in pkgutil.walk_packages(
            discolike.resources.__path__, prefix=f"{discolike.resources.__name__}."
        )
    )
    return modules


def _request_model(member: object) -> type[DiscolikeRequest] | None:
    for annotation in typing.get_type_hints(member).values():
        for candidate in (annotation, *typing.get_args(annotation)):
            if inspect.isclass(candidate) and issubclass(candidate, DiscolikeRequest):
                return candidate
    return None


def _body_arguments(*, class_name: str, method_name: str, member: object) -> dict[str, Any]:
    mapping = BODY_BUILDERS.get((class_name, method_name))
    if mapping is None:
        return {}
    hints = typing.get_type_hints(member)
    return {body_field: hints[argument] for argument, body_field in mapping.items()}


def collect_routes() -> list[RouteEntry]:
    seen: dict[tuple[str, str], RouteEntry] = {}
    for module in _resource_modules():
        for class_name, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ != module.__name__ or class_name.startswith(ASYNC_CLASS_PREFIX):
                continue
            for method_name, member in vars(cls).items():
                if not inspect.isfunction(member):
                    continue
                route = get_discolike_route(member)
                if route is None:
                    continue
                http_method, path, openapi = route
                key = (class_name, method_name)
                if key in seen:
                    continue
                body_arguments = _body_arguments(class_name=class_name, method_name=method_name, member=member)
                request_model = None if body_arguments else _request_model(member)
                seen[key] = RouteEntry(
                    class_name, method_name, http_method, path, openapi, request_model, body_arguments
                )
    return list(seen.values())


def _resolve_ref(*, spec: dict, schema: dict) -> dict:
    ref = schema.get("$ref")
    if ref is None:
        return schema
    node = spec
    for part in ref.lstrip("#/").split("/"):
        node = node[part]
    return node


def _request_body_properties(*, spec: dict, operation: dict) -> dict[str, dict]:
    content = operation.get("requestBody", {}).get("content", {})
    for media_type in content.values():
        schema = _resolve_ref(spec=spec, schema=media_type.get("schema", {}))
        return schema.get("properties", {})
    return {}


def _spec_request_fields(*, spec: dict, operation: dict) -> set[str]:
    fields = {
        parameter["name"]
        for parameter in operation.get("parameters", [])
        if parameter["in"] == QUERY_LOCATION
        and not parameter.get("deprecated", False)
        and not parameter.get("schema", {}).get("deprecated", False)
    }
    fields |= {
        name
        for name, prop in _request_body_properties(spec=spec, operation=operation).items()
        if not prop.get("deprecated", False)
    }
    return fields - IGNORE_PARAMS


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
        if route.body_arguments:
            mismatches.extend(
                _check_body_arguments(spec=spec, operation=operation, label=label, arguments=route.body_arguments)
            )
            continue
        spec_fields = _spec_request_fields(spec=spec, operation=operation)
        if route.request_model is None:
            mismatches.extend(
                f"{label}: spec has param '{field}' but the method takes no request model"
                for field in sorted(spec_fields)
            )
            continue
        model = route.request_model
        model_fields = set(model.model_fields) - HIDDEN_REQUEST_FIELDS.get(model.__name__, frozenset())
        mismatches.extend(
            f"{label}: field '{field}' of {model.__name__} not found in spec"
            for field in sorted(model_fields - spec_fields)
        )
        mismatches.extend(
            f"{label}: spec param '{field}' not declared on {model.__name__}"
            for field in sorted(spec_fields - model_fields)
        )
    return mismatches


def _check_body_arguments(*, spec: dict, operation: dict, label: str, arguments: dict[str, Any]) -> list[str]:
    properties = _request_body_properties(spec=spec, operation=operation)
    mismatches: list[str] = []
    for body_field, annotation in sorted(arguments.items()):
        prop = properties.get(body_field)
        if prop is None:
            mismatches.append(f"{label}: builds body field '{body_field}' not found in spec")
            continue
        mismatches.extend(
            _mapping_mismatches(spec=spec, label=label, body_field=body_field, annotation=annotation, prop=prop)
        )
    return mismatches


def _mapping_type(annotation: Any) -> tuple[Any, ...] | None:  # noqa: ANN401 -- arbitrary type hint
    for candidate in (annotation, *typing.get_args(annotation)):
        if typing.get_origin(candidate) is dict:
            return typing.get_args(candidate)
    return None


def _mapping_mismatches(*, spec: dict, label: str, body_field: str, annotation: Any, prop: dict) -> list[str]:  # noqa: ANN401
    mapping = _mapping_type(annotation)
    if mapping is None:
        return []
    key_type, value_type = mapping
    variant = next((variant for variant in _type_variants(prop) if "additionalProperties" in variant), None)
    if variant is None:
        return [f"{label}: body field '{body_field}' is a mapping in the SDK but not in the spec"]
    mismatches: list[str] = []
    spec_keys = set(variant.get("propertyNames", {}).get("enum", []))
    if typing.get_origin(key_type) is Literal and not spec_keys:
        mismatches.append(f"{label}: spec accepts any key of body field '{body_field}' but the SDK restricts them")
    elif typing.get_origin(key_type) is Literal:
        sdk_keys = set(typing.get_args(key_type))
        mismatches.extend(
            f"{label}: key '{key}' of body field '{body_field}' not found in spec"
            for key in sorted(sdk_keys - spec_keys)
        )
        mismatches.extend(
            f"{label}: spec key '{key}' of body field '{body_field}' not accepted by the SDK"
            for key in sorted(spec_keys - sdk_keys)
        )
    value_schema = variant["additionalProperties"]
    if inspect.isclass(value_type) and issubclass(value_type, DiscolikeRequest) and isinstance(value_schema, dict):
        spec_fields = set(_resolve_ref(spec=spec, schema=value_schema).get("properties", {}))
        model_fields = set(value_type.model_fields)
        mismatches.extend(
            f"{label}: field '{name}' of {value_type.__name__} not found in spec"
            for name in sorted(model_fields - spec_fields)
        )
        mismatches.extend(
            f"{label}: spec param '{name}' not declared on {value_type.__name__}"
            for name in sorted(spec_fields - model_fields)
        )
    return mismatches


TYPE_INFO_KEYS = {"type", "anyOf", "oneOf", "$ref", "nullable"}
FieldShape = tuple[frozenset[str], str | None]


def _resolved_type(node: dict, *, root: dict) -> str | None:
    """A $ref resolves to its target's type, so a named enum alias reads as "string" rather than "object"."""
    ref = node.get("$ref")
    if ref is None:
        return node.get("type")
    target: object = root
    for part in ref.lstrip("#/").split("/"):
        target = target.get(part) if isinstance(target, dict) else None
    return target.get("type", "object") if isinstance(target, dict) else "object"


def _type_variants(prop: dict) -> list[dict]:
    return prop.get("anyOf") or prop.get("oneOf") or [prop]


def _field_types(prop: dict, *, root: dict) -> frozenset[str]:
    types = {
        resolved for variant in _type_variants(prop) if (resolved := _resolved_type(variant, root=root)) is not None
    }
    if prop.get("nullable"):
        types.add("null")
    return frozenset(types)


def _item_type(prop: dict, *, root: dict) -> str | None:
    for variant in _type_variants(prop):
        items = variant.get("items")
        if items is not None:
            return _resolved_type(items, root=root)
    return None


def _has_type_info(prop: dict) -> bool:
    return bool(prop.keys() & TYPE_INFO_KEYS)


def _field_shape(prop: dict, *, root: dict) -> FieldShape:
    return (_field_types(prop, root=root), _item_type(prop, root=root))


def _describe(shape: FieldShape) -> str:
    types = " | ".join(sorted(shape[0]))
    return types if shape[1] is None else f"{types} of {shape[1]}"


def _accepts(*, model_shape: FieldShape, spec_shape: FieldShape) -> bool:
    return spec_shape[0] <= model_shape[0] and ("array" not in spec_shape[0] or spec_shape[1] == model_shape[1])


def check_models(spec: dict, mirrored: dict[str, type[DiscolikeModel]] | None = None) -> list[str]:
    mismatches: list[str] = []
    schemas = spec.get("components", {}).get("schemas", {})
    for schema_name, model in (MIRRORED_SCHEMAS if mirrored is None else mirrored).items():
        schema = schemas.get(schema_name)
        if schema is None:
            mismatches.append(f"{model.__name__}: schema '{schema_name}' not found in spec")
            continue
        spec_properties = schema.get("properties", {})
        spec_fields = set(spec_properties)
        model_schema = model.model_json_schema()
        model_properties = model_schema.get("properties", {})
        model_fields = set(model.model_fields)
        mismatches.extend(
            f"{model.__name__}: field '{field}' not in spec schema '{schema_name}'"
            for field in sorted(model_fields - spec_fields)
        )
        mismatches.extend(
            f"{model.__name__}: spec schema '{schema_name}' has field '{field}' the SDK does not declare"
            for field in sorted(spec_fields - model_fields)
        )

        # A fixture that doesn't spell out "type"/"required" info is asserting nothing about it, not
        # that nothing is required or typed, so leave those fields alone rather than flag every one.
        # Only drift that breaks parsing is flagged: an SDK looser than the spec still reads every response.
        if "required" in schema:
            mismatches.extend(
                f"{model.__name__}: field '{field}' is optional in spec schema '{schema_name}' but required on "
                f"the SDK model"
                for field in sorted((set(model_schema.get("required", [])) - set(schema["required"])) & spec_fields)
            )

        for field in sorted(model_fields & spec_fields):
            spec_prop = spec_properties[field]
            if not _has_type_info(spec_prop):
                continue
            model_shape = _field_shape(model_properties.get(field, {}), root=model_schema)
            spec_shape = _field_shape(spec_prop, root=spec)
            if not _accepts(model_shape=model_shape, spec_shape=spec_shape):
                mismatches.append(
                    f"{model.__name__}: field '{field}' has type {_describe(model_shape)} but spec schema "
                    f"'{schema_name}' declares {_describe(spec_shape)}"
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
