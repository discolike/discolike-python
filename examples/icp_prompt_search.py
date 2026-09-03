"""Describe your ideal customer in plain English and print the matching companies with their similarity score."""

from __future__ import annotations

import argparse

from discolike import Discolike
from discolike.requests import DiscoverParams


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", help="Natural-language ICP, e.g. 'Series A fintechs in Europe selling to SMBs'")
    parser.add_argument("--country", action="append", help="ISO-2 country code or region alias, repeatable")
    parser.add_argument("--max-records", type=int, default=25, help="Companies to return (5-10000, default 25)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = Discolike()
    companies = client.discover(
        DiscoverParams(icp_prompt=args.prompt, country=args.country, max_records=args.max_records)
    )
    print(f"{'domain':<32} {'name':<40} similarity")
    for company in companies:
        similarity = f"{company.similarity:.0f}" if company.similarity is not None else "-"
        print(f"{company.domain or '':<32} {(company.name or '')[:40]:<40} {similarity}")
    print(f"\n{len(companies)} companies for: {args.prompt!r}")


if __name__ == "__main__":
    main()
