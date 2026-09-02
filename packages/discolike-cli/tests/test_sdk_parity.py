"""Every SDK request field must be reachable as a first-class CLI flag.

Reads the CLI source with ``ast`` rather than invoking typer, so a new field on
a request model fails here until the matching command forwards it.
"""

from __future__ import annotations

import ast
import pathlib
from collections.abc import Iterator

import pytest

import discolike.requests as requests_module

CLI_SOURCE_DIR = pathlib.Path(__file__).resolve().parents[1] / "src" / "discolike_cli"
REQUEST_BUILDER = "build_request"
# icp_text was dropped from discover and contacts in 0.1.1 in favor of icp_prompt; see the *_icp_text_*_removed tests.
DELIBERATELY_OMITTED: dict[str, frozenset[str]] = {
    "DiscoverParams": frozenset({"icp_text"}),
    "ContactsSearchParams": frozenset({"icp_text"}),
    "ContactsCountParams": frozenset({"icp_text"}),
    "ContactFilters": frozenset({"icp_text"}),
}
DICT_ONLY_FIELDS: dict[str, frozenset[str]] = {
    "ContactGenerateRequest": frozenset({"initial_contact_counts"}),
    "DiscoGenProcessRequest": frozenset({"previous_discogen_data"}),
    "DiscoGenPersonaProcessRequest": frozenset({"previous_discogen_data"}),
    "SaveResultsRequest": frozenset({"query_params"}),
}


def _keyword_names(call: ast.Call) -> set[str]:
    return {keyword.arg for keyword in call.keywords if keyword.arg is not None}


def _dict_keys(node: ast.Dict, assignments: dict[str, ast.Call]) -> set[str]:
    keys: set[str] = set()
    for key, value in zip(node.keys, node.values, strict=True):
        if key is None:
            keys |= _forwarded_fields(argument=value, assignments=assignments)
        elif isinstance(key, ast.Constant) and isinstance(key.value, str):
            keys.add(key.value)
    return keys


def _forwarded_fields(argument: ast.expr, assignments: dict[str, ast.Call]) -> set[str]:
    if isinstance(argument, ast.Name) and argument.id in assignments:
        argument = assignments[argument.id]
    if isinstance(argument, ast.Call):
        return _keyword_names(argument)
    if isinstance(argument, ast.Dict):
        return _dict_keys(node=argument, assignments=assignments)
    return set()


def _build_request_sites() -> Iterator[tuple[str, str, set[str]]]:
    for source_file in sorted(CLI_SOURCE_DIR.glob("*.py")):
        tree = ast.parse(source_file.read_text())
        for function in (node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)):
            assignments = {
                node.targets[0].id: node.value
                for node in ast.walk(function)
                if isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Call)
            }
            for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
                callee = call.func.id if isinstance(call.func, ast.Name) else getattr(call.func, "attr", "")
                if callee != REQUEST_BUILDER or not call.args or not isinstance(call.args[0], ast.Name):
                    continue
                forwarded: set[str] = set()
                for argument in call.args[1:]:
                    forwarded |= _forwarded_fields(argument=argument, assignments=assignments)
                yield f"{source_file.stem}.{function.name}", call.args[0].id, forwarded


SITES = list(_build_request_sites())


@pytest.mark.parametrize(("site", "model_name", "forwarded"), SITES, ids=[f"{s}->{m}" for s, m, _ in SITES])
def test_cli_forwards_every_sdk_field(site: str, model_name: str, forwarded: set[str]) -> None:
    model = getattr(requests_module, model_name)
    excluded = DICT_ONLY_FIELDS.get(model_name, frozenset()) | DELIBERATELY_OMITTED.get(model_name, frozenset())
    expected = set(model.model_fields) - excluded
    missing = sorted(expected - forwarded)
    assert not missing, f"{site} does not forward {model_name} fields: {', '.join(missing)}"


def test_every_request_model_has_a_cli_command() -> None:
    used = {model_name for _, model_name, _ in SITES}
    declared = {
        name
        for name in dir(requests_module)
        if name.endswith(("Params", "Request")) and hasattr(getattr(requests_module, name), "model_fields")
    }
    assert not sorted(declared - used), f"request models with no CLI command: {sorted(declared - used)}"
