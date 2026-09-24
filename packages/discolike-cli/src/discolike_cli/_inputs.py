"""File-backed inputs for volume flows: domain lists and whole-request JSON."""

from __future__ import annotations

import csv
import json
import pathlib
from typing import Any

import typer

DOMAIN_COLUMN = "domain"
WWW_PREFIX = "www."


def read_domains_file(path: pathlib.Path) -> list[str]:
    """CSV with a ``domain`` column, or one domain per line (first column when no header).

    Domains are stripped, lower-cased, ``www.``-less and de-duplicated in file order.
    """
    try:
        with path.open(newline="") as handle:
            rows = list(csv.reader(handle))
    except FileNotFoundError as exc:
        raise typer.BadParameter(f"domains file not found: {path}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise typer.BadParameter(f"domains file {path} could not be read: {exc}") from exc
    header = [cell.strip().lower() for cell in rows[0]] if rows else []
    column = header.index(DOMAIN_COLUMN) if DOMAIN_COLUMN in header else 0
    body = rows[1:] if DOMAIN_COLUMN in header else rows
    seen: set[str] = set()
    domains: list[str] = []
    for row in body:
        if column >= len(row):
            continue
        domain = row[column].strip().lower().removeprefix(WWW_PREFIX)
        if domain and domain not in seen:
            seen.add(domain)
            domains.append(domain)
    if not domains:
        raise typer.BadParameter(f"domains file has no domains: {path}")
    return domains


def read_params_file(path: pathlib.Path) -> dict[str, Any]:
    """JSON object of API parameter names, e.g. an app form copied over verbatim."""
    try:
        loaded = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise typer.BadParameter(f"params file not found: {path}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise typer.BadParameter(f"params file {path} could not be read: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"params file {path} must contain valid JSON: {exc}") from exc
    if not isinstance(loaded, dict):
        raise typer.BadParameter(f"params file {path} must contain a JSON object")
    return loaded


def merge_domains(inline: list[str] | None, file: pathlib.Path | None) -> list[str] | None:
    """Inline ``--domain`` values first, then the file's, or ``None`` when neither was given."""
    if file is None:
        return inline
    return [*(inline or []), *read_domains_file(file)]
