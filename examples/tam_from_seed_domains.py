"""Size a market from three seed domains: count the country + size bucket first, then discover lookalikes into a CSV."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from discolike import Discolike
from discolike.requests import CountParams
from discolike.requests import DiscoverParams

SEED_DOMAIN_COUNT = 3
OUTPUT_FIELDS = ["domain", "name", "similarity", "employees", "country", "description"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "domains", nargs=SEED_DOMAIN_COUNT, help="Three seed domains, e.g. stripe.com adyen.com checkout.com"
    )
    parser.add_argument("country", help="ISO-2 country code or region alias, e.g. US, DE, EU, DACH")
    parser.add_argument("employee_range", help="Employee range as 'min,max', e.g. 51,200")
    parser.add_argument("--max-records", type=int, default=100, help="Companies to discover (5-10000, default 100)")
    parser.add_argument("--output", type=Path, default=Path("tam.csv"), help="Output CSV path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = Discolike()

    ceiling = client.count(CountParams(country=[args.country], employee_range=args.employee_range))
    print(f"Companies in {args.country} with {args.employee_range} employees: {ceiling.count}")

    companies = client.discover(
        DiscoverParams(
            domain=args.domains,
            country=[args.country],
            employee_range=args.employee_range,
            max_records=args.max_records,
        )
    )
    if not companies:
        sys.exit("No lookalikes found; loosen the country or employee range.")

    with args.output.open(mode="w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for company in companies:
            writer.writerow(
                {
                    "domain": company.domain or "",
                    "name": company.name or "",
                    "similarity": company.similarity if company.similarity is not None else "",
                    "employees": company.employees or "",
                    "country": company.address.country if company.address else "",
                    "description": company.description or "",
                }
            )
    print(f"Wrote {len(companies)} lookalikes of {', '.join(args.domains)} to {args.output}")


if __name__ == "__main__":
    main()
