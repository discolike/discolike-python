from __future__ import annotations

from pathlib import Path

import pytest
import typer

from discolike_cli._inputs import read_domains_file
from discolike_cli._inputs import read_params_file


def test_read_domains_file_one_per_line_normalizes_and_dedupes(tmp_path: Path) -> None:
    path = tmp_path / "domains.txt"
    path.write_text("Acme.com\nwww.beta.io\n\n  acme.com \n")
    assert read_domains_file(path) == ["acme.com", "beta.io"]


def test_read_domains_file_csv_uses_domain_column(tmp_path: Path) -> None:
    path = tmp_path / "companies.csv"
    path.write_text("name,Domain,country\nAcme,acme.com,US\nBeta,beta.io,DE\n")
    assert read_domains_file(path) == ["acme.com", "beta.io"]


def test_read_domains_file_csv_without_domain_header_uses_first_column(tmp_path: Path) -> None:
    path = tmp_path / "companies.csv"
    path.write_text("acme.com,Acme\nbeta.io,Beta\n")
    assert read_domains_file(path) == ["acme.com", "beta.io"]


def test_read_domains_file_missing_is_bad_parameter(tmp_path: Path) -> None:
    with pytest.raises(typer.BadParameter, match="not found"):
        read_domains_file(tmp_path / "nope.csv")


def test_read_domains_file_empty_is_bad_parameter(tmp_path: Path) -> None:
    path = tmp_path / "empty.txt"
    path.write_text("\n\n")
    with pytest.raises(typer.BadParameter, match="no domains"):
        read_domains_file(path)


def test_read_params_file_returns_object(tmp_path: Path) -> None:
    path = tmp_path / "form.json"
    path.write_text('{"country": ["US"], "variance": "MID_HIGH"}')
    assert read_params_file(path) == {"country": ["US"], "variance": "MID_HIGH"}


def test_read_params_file_rejects_non_object(tmp_path: Path) -> None:
    path = tmp_path / "form.json"
    path.write_text("[1, 2]")
    with pytest.raises(typer.BadParameter, match="JSON object"):
        read_params_file(path)


def test_read_params_file_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "form.json"
    path.write_text("{nope")
    with pytest.raises(typer.BadParameter, match="valid JSON"):
        read_params_file(path)


def test_read_params_file_missing_is_bad_parameter(tmp_path: Path) -> None:
    with pytest.raises(typer.BadParameter, match="not found"):
        read_params_file(tmp_path / "nope.json")


def test_read_domains_file_directory_is_bad_parameter(tmp_path: Path) -> None:
    with pytest.raises(typer.BadParameter, match="could not be read"):
        read_domains_file(tmp_path)


def test_read_domains_file_bad_encoding_is_bad_parameter(tmp_path: Path) -> None:
    path = tmp_path / "latin1.csv"
    path.write_bytes(b"caf\xe9.com\n")
    with pytest.raises(typer.BadParameter, match="could not be read"):
        read_domains_file(path)


def test_read_params_file_directory_is_bad_parameter(tmp_path: Path) -> None:
    with pytest.raises(typer.BadParameter, match="could not be read"):
        read_params_file(tmp_path)
