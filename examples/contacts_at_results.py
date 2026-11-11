"""Automatically find and deliver validated decision-maker contacts for a company ICP."""

from __future__ import annotations

import argparse

from discolike import Discolike
from discolike.requests import ContactsRunRequest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", help="Natural-language ICP for the company search")
    parser.add_argument("--country", action="append", help="ISO-2 country code or region alias, repeatable")
    parser.add_argument(
        "--top", type=int, default=10, help="Target companies delivering validated contacts (default 10)"
    )
    parser.add_argument("--fit", default="Senior executives and decision makers", help="Describe the people to find")
    parser.add_argument("--per-company", type=int, default=3, help="Validated contacts per company (default 3)")
    parser.add_argument("--email-cap-usd", type=float, help="Maximum delivery spend in USD; omit for no cap")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    body = {
        "companies": {
            "source": "prompt",
            "icp_text": args.prompt,
            "filters": {"filter_country": args.country} if args.country else {},
        },
        "people": {"fit": args.fit},
        "max_companies": args.top,
        "per_company": args.per_company,
    }
    if args.email_cap_usd is not None:
        body["email_cap_usd"] = args.email_cap_usd
    with Discolike() as client:
        run = client.contacts_run.create(ContactsRunRequest.model_validate(body))
        print(f"Run {run.id}: {run.status}")
        run = client.contacts_run.wait(run.id)
        print(f"Finished: {run.status}; summary: {run.summary}")
        for contact in client.contacts_run.rows(run.id):
            print(
                f"{contact.domain}\t{contact.name or ''}\t{contact.title or ''}\t{contact.email or ''}\t{contact.email_status or ''}"
            )


if __name__ == "__main__":
    main()
