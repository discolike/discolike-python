"""Open a DiscoLike account for a person, then run a first search once their key exists.

signup() posts {email, first_name, last_name, agent} to https://api.discolike.com/v1/public/signup with no
auth header and returns a next_step message to relay to the person. No API key comes back: the person
confirms their email, logs in at https://app.discolike.com, and creates a key under Account > API keys.
Export that key as DISCOLIKE_API_KEY and rerun this script to make the first discover call.
"""

from __future__ import annotations

import argparse
import os

from discolike import Discolike
from discolike import DiscolikeError
from discolike import signup
from discolike.requests import DiscoverParams

AGENT_NAME = "cookbook"
API_KEY_ENV = "DISCOLIKE_API_KEY"
FIRST_SEARCH_PROMPT = "B2B SaaS companies selling to sales teams"
FIRST_SEARCH_RECORDS = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", help="Work email of the person the account is for")
    parser.add_argument("--first-name", help="Their first name")
    parser.add_argument("--last-name", help="Their last name")
    parser.add_argument("--allow-new-email", action="store_true", help="Sign up a second email from this machine")
    return parser.parse_args()


def run_signup(args: argparse.Namespace) -> None:
    try:
        result = signup(
            email=args.email,
            first_name=args.first_name,
            last_name=args.last_name,
            agent=AGENT_NAME,
            allow_new_email=args.allow_new_email,
        )
    except DiscolikeError as exc:
        print(f"Signup failed: {exc}")
        return
    print(f"Signup {result.status} for {result.email} (org {result.org_domain}: {result.org_status})")
    print(f"Next step: {result.next_step}")


def run_first_search() -> None:
    client = Discolike()
    companies = client.discover(DiscoverParams(icp_prompt=FIRST_SEARCH_PROMPT, max_records=FIRST_SEARCH_RECORDS))
    print(f"\nFirst search, {FIRST_SEARCH_PROMPT!r}:")
    for company in companies:
        print(f"  {company.domain or '':<32} {company.name or ''}")


def main() -> None:
    args = parse_args()
    if args.email and args.first_name and args.last_name:
        run_signup(args)
    else:
        print("No --email/--first-name/--last-name given, skipping signup.")
    if os.environ.get(API_KEY_ENV):
        run_first_search()
    else:
        print(f"\n{API_KEY_ENV} is not set; export it after email confirmation and rerun for the first search.")


if __name__ == "__main__":
    main()
