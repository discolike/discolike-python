"""Discover companies for an ICP, then find decision makers at the top N by seniority, department, or title."""

from __future__ import annotations

import argparse

from discolike import Discolike
from discolike.requests import ContactsSearchParams
from discolike.requests import DiscoverParams

SENIORITIES = ["executive", "vp", "director", "manager", "senior_ic", "mid_level", "entry_level"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", help="Natural-language ICP for the company search")
    parser.add_argument("--country", action="append", help="ISO-2 country code or region alias, repeatable")
    parser.add_argument("--top", type=int, default=10, help="Companies to search contacts at (default 10)")
    parser.add_argument("--seniority", action="append", choices=SENIORITIES, help="Persona seniority, repeatable")
    parser.add_argument("--department", action="append", help="Persona department, e.g. 'Sales - Marketing'")
    parser.add_argument("--title", action="append", help="Job title term, e.g. 'Head of Growth', repeatable")
    parser.add_argument("--per-company", type=int, default=3, help="Contacts per company (default 3)")
    parser.add_argument("--has-email", action="store_true", help="Only contacts with an email address")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = Discolike()

    companies = client.discover(
        DiscoverParams(icp_prompt=args.prompt, country=args.country, max_records=max(args.top, 5))
    )
    domains = [company.domain for company in companies[: args.top] if company.domain]
    print(f"Top {len(domains)} companies: {', '.join(domains)}")

    contacts = client.contacts.search(
        ContactsSearchParams(
            domain=domains,
            seniority=args.seniority,
            department=args.department,
            title=args.title,
            has_email=args.has_email,
            results_by_company=args.per_company,
            max_records=max(len(domains) * args.per_company, 20),
        )
    )
    print(f"\n{'domain':<28} {'name':<28} {'title':<40} email")
    for contact in contacts:
        print(
            f"{contact.domain or '':<28} {(contact.name or '')[:28]:<28} "
            f"{(contact.title or '')[:40]:<40} {contact.email or ''}"
        )
    print(f"\n{len(contacts)} contacts across {len({contact.domain for contact in contacts})} companies")


if __name__ == "__main__":
    main()
