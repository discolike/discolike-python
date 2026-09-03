"""Find companies whose website contains an exact phrase: count the match first, then pull the list."""

from __future__ import annotations

import argparse

from discolike import Discolike
from discolike.requests import CountParams
from discolike.requests import DiscoverParams


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phrase", nargs="+", help="Phrases the site must contain (up to 20, 3+ chars each)")
    parser.add_argument("--country", action="append", required=True, help="ISO-2 country code or region alias")
    parser.add_argument("--max-records", type=int, default=50, help="Companies to return (5-10000, default 50)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = Discolike()

    total = client.count(CountParams(phrase_match=args.phrase, country=args.country))
    print(f"{total.count} sites in {', '.join(args.country)} mention {args.phrase}")

    companies = client.discover(
        DiscoverParams(phrase_match=args.phrase, country=args.country, max_records=args.max_records)
    )
    for company in companies:
        print(f"{company.domain or '':<32} {company.name or ''}")
    print(f"\nShowing {len(companies)} of {total.count}")


if __name__ == "__main__":
    main()
