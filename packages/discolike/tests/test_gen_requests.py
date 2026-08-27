import importlib.util
import pathlib
import sys
from typing import Any

import pytest

SCRIPT_PATH = pathlib.Path(__file__).parents[3] / "scripts" / "gen_requests.py"

FAKE_SPEC: dict[str, Any] = {
    "openapi": "3.1.0",
    "paths": {
        "/match": {
            "get": {
                "parameters": [
                    {"name": "name", "in": "query", "required": True, "schema": {"type": "string"}},
                    {
                        "name": "city",
                        "in": "query",
                        "required": False,
                        "schema": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    },
                    {
                        "name": "nl_match",
                        "in": "query",
                        "required": False,
                        "deprecated": True,
                        "schema": {"type": "string"},
                    },
                ]
            }
        },
        "/bulkmatch": {
            "post": {
                "parameters": [{"name": "name_column", "in": "query", "required": True, "schema": {"type": "string"}}],
                "requestBody": {
                    "content": {"multipart/form-data": {"schema": {"$ref": "#/components/schemas/Body_bulk_match"}}}
                },
            }
        },
        "/email/find/batch": {
            "post": {
                "requestBody": {
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/FindEmailBatchRequest"}}}
                }
            }
        },
        "/usage": {"get": {"parameters": []}},
    },
    "components": {
        "schemas": {
            "Body_bulk_match": {
                "type": "object",
                "properties": {"file": {"type": "string", "format": "binary"}},
                "required": ["file"],
            },
            "FindEmailBatchRequest": {
                "type": "object",
                "properties": {
                    "requests": {"type": "array", "items": {"$ref": "#/components/schemas/FindEmailRequest"}}
                },
                "required": ["requests"],
            },
            "FindEmailRequest": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "first_name": {"type": "string"},
                    "known_pattern": {
                        "anyOf": [{"type": "string", "maxLength": 40}, {"type": "null"}],
                        "description": "Known pattern",
                    },
                    "legacy": {"type": "string", "deprecated": True},
                },
                "required": ["first_name"],
            },
            "Unrelated": {"type": "object", "properties": {"x": {"type": "integer"}}},
        }
    },
}


SIBLING_REF_SPEC: dict[str, Any] = {
    "components": {
        "schemas": {
            "Root": {
                "type": "object",
                "properties": {
                    "zebra": {"$ref": "#/components/schemas/Zebra"},
                    "alpha": {"$ref": "#/components/schemas/Alpha"},
                    "middle": {"$ref": "#/components/schemas/Middle"},
                },
            },
            "Zebra": {"type": "object", "properties": {"z": {"type": "string"}}},
            "Alpha": {"type": "object", "properties": {"a": {"type": "string"}}},
            "Middle": {"type": "object", "properties": {"m": {"type": "string"}}},
        }
    }
}


@pytest.fixture(scope="module")
def gen():
    spec = importlib.util.spec_from_file_location("gen_requests", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def routes(gen):
    return [
        gen.Route("MatchResource", "company", "GET", "/match"),
        gen.Route("MatchResource", "bulk", "POST", "/bulkmatch"),
        gen.Route("EmailResource", "find_batch", "POST", "/email/find/batch"),
        gen.Route("AccountResource", "usage", "GET", "/usage"),
    ]


@pytest.mark.parametrize(
    ("class_name", "method_name", "expected"),
    [
        ("MatchResource", "company", "MatchCompanyParams"),
        ("CompaniesResource", "public_links", "CompaniesPublicLinksParams"),
        ("EnrichResource", "segment_file", "SegmentFileParams"),
        ("DiscoveryResource", "discover", "DiscoverParams"),
        ("ValidateResource", "icp", "IcpParams"),
    ],
)
def test_params_model_name(gen, class_name, method_name, expected):
    assert gen.params_model_name(class_name=class_name, method_name=method_name) == expected


def test_request_schemas_synthesizes_params_from_query_parameters(gen, routes):
    schemas = gen.request_schemas(spec=FAKE_SPEC, routes=routes)
    assert schemas["MatchCompanyParams"] == {
        "type": "object",
        "properties": {"name": {"type": "string"}, "city": {"anyOf": [{"type": "string"}, {"type": "null"}]}},
        "required": ["name"],
    }


def test_request_schemas_skips_multipart_body_and_keeps_query_params(gen, routes):
    schemas = gen.request_schemas(spec=FAKE_SPEC, routes=routes)
    assert schemas["MatchBulkParams"] == {
        "type": "object",
        "properties": {"name_column": {"type": "string"}},
        "required": ["name_column"],
    }
    assert "Body_bulk_match" not in schemas


def test_request_schemas_uses_the_json_body_component_name(gen, routes):
    schemas = gen.request_schemas(spec=FAKE_SPEC, routes=routes)
    assert schemas["FindEmailBatchRequest"] == FAKE_SPEC["components"]["schemas"]["FindEmailBatchRequest"]


def test_request_schemas_emits_nothing_for_routes_without_params(gen, routes):
    schemas = gen.request_schemas(spec=FAKE_SPEC, routes=routes)
    assert "AccountUsageParams" not in schemas


def test_request_schemas_fails_loudly_when_a_route_is_missing_from_the_spec(gen):
    with pytest.raises(SystemExit, match="GET /nowhere"):
        gen.request_schemas(spec=FAKE_SPEC, routes=[gen.Route("X", "y", "GET", "/nowhere")])


def test_prune_keeps_transitive_refs_and_drops_unrelated_schemas(gen, routes):
    requested = {"FindEmailBatchRequest": FAKE_SPEC["components"]["schemas"]["FindEmailBatchRequest"]}
    assert set(gen.prune(spec=FAKE_SPEC, requested=requested)) == {"FindEmailBatchRequest", "FindEmailRequest"}


def test_prune_orders_sibling_refs_deterministically(gen):
    requested = {"Root": SIBLING_REF_SPEC["components"]["schemas"]["Root"]}
    kept = list(gen.prune(spec=SIBLING_REF_SPEC, requested=requested))
    assert kept == ["Root", "Alpha", "Middle", "Zebra"]
    assert kept == list(gen.prune(spec=SIBLING_REF_SPEC, requested=requested))


def test_normalize_schema_inlines_nullable_and_drops_deprecated_and_additional_properties(gen):
    normalized = gen.normalize_schema(FAKE_SPEC["components"]["schemas"]["FindEmailRequest"])
    assert "additionalProperties" not in normalized
    assert "legacy" not in normalized["properties"]
    assert normalized["properties"]["known_pattern"] == {
        "type": "string",
        "maxLength": 40,
        "description": "Known pattern",
        "nullable": True,
    }
    assert normalized["required"] == ["first_name"]


def test_normalize_schema_leaves_required_nullable_unions_alone(gen):
    schema = {
        "type": "object",
        "properties": {"api_key": {"anyOf": [{"type": "string"}, {"type": "null"}]}},
        "required": ["api_key"],
    }
    assert gen.normalize_schema(schema)["properties"]["api_key"] == {"anyOf": [{"type": "string"}, {"type": "null"}]}


def test_normalize_schema_strips_scalar_item_constraints(gen):
    schema = {
        "type": "object",
        "properties": {"tags": {"type": "array", "items": {"type": "string", "minLength": 3}, "maxItems": 20}},
    }
    assert gen.normalize_schema(schema)["properties"]["tags"] == {
        "type": "array",
        "items": {"type": "string"},
        "maxItems": 20,
    }


def test_build_codegen_spec_wraps_pruned_schemas(gen, routes):
    codegen_spec = gen.build_codegen_spec(spec=FAKE_SPEC, routes=routes)
    assert codegen_spec["paths"] == {}
    assert set(codegen_spec["components"]["schemas"]) == {
        "MatchCompanyParams",
        "MatchBulkParams",
        "FindEmailBatchRequest",
        "FindEmailRequest",
    }


def test_compare_returns_zero_when_identical(gen, capsys):
    assert gen.compare(committed="a\n", fresh="a\n") == 0
    assert "up to date" in capsys.readouterr().out


def test_compare_prints_a_diff_and_returns_one_on_drift(gen, capsys):
    assert gen.compare(committed="a\n", fresh="b\n") == 1
    out = capsys.readouterr().out
    assert "-a" in out
    assert "+b" in out
    assert "gen_requests.py" in out


def test_collect_routes_covers_every_stamped_sync_route(gen):
    routes = gen.collect_routes()
    assert len(routes) == 48
    assert all(not route.class_name.startswith("Async") for route in routes)
