"""Enrich a CSV of domains with firmographics from the company profile endpoint and write a widened CSV."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from discolike import Discolike
from discolike import DiscolikeError
from discolike.requests import CompaniesDataParams

ENRICHED_FIELDS = [
    "dl_name",
    "dl_employees",
    "dl_revenue_range",
    "dl_country",
    "dl_state",
    "dl_city",
    "dl_industry_groups",
    "dl_business_model",
    "dl_description",
    "dl_error",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="CSV with a domain column")
    parser.add_argument("--output", type=Path, default=Path("enriched.csv"), help="Output CSV path")
    parser.add_argument("--domain-column", default="domain", help="Column holding the domain (default: domain)")
    return parser.parse_args()


def top_keys(weights: dict[str, float], *, limit: int = 3) -> str:
    return "; ".join(key for key, _ in sorted(weights.items(), key=lambda item: item[1], reverse=True)[:limit])


def enrich_row(client: Discolike, *, domain: str) -> dict[str, str]:
    try:
        profile = client.companies.data(CompaniesDataParams(domain=domain))
    except DiscolikeError as exc:
        return {"dl_error": str(exc)}
    address = profile.address
    return {
        "dl_name": profile.name or "",
        "dl_employees": profile.employees or "",
        "dl_revenue_range": profile.revenue_range or "",
        "dl_country": address.country if address else "",
        "dl_state": address.state if address else "",
        "dl_city": address.city if address else "",
        "dl_industry_groups": top_keys(profile.industry_groups),
        "dl_business_model": top_keys(profile.business_model),
        "dl_description": profile.description or "",
        "dl_error": "",
    }


def main() -> None:
    args = parse_args()
    with args.input.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    if args.domain_column not in fieldnames:
        sys.exit(f"Column {args.domain_column!r} not found in {args.input}; columns are {fieldnames}")

    client = Discolike()
    enriched = 0
    with args.output.open(mode="w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames + ENRICHED_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            domain = row[args.domain_column].strip().lower().removeprefix("www.")
            extra = enrich_row(client, domain=domain) if domain else {"dl_error": "empty domain"}
            if not extra.get("dl_error"):
                enriched += 1
            writer.writerow({**row, **extra})
    print(f"Enriched {enriched}/{len(rows)} rows -> {args.output}")


if __name__ == "__main__":
    main()
