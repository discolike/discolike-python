"""Discover companies matching an ICP, then enrich them with DiscoGen.

Two calls end to end:

1. ``client.discover(icp_text=..., country=..., max_records=...)`` finds
   lookalike companies from DiscoLike's index of 80M+ business websites.
2. ``client.discogen.process(query=..., domains=[...], web_search=True)``
   runs an AI research prompt over the discovered domains and returns one
   structured answer per company. ``job.wait()`` blocks until it finishes.

DiscoGen runs on your own LLM provider key (BYOK) - configure one first via
``client.llm_providers`` or in the app under Settings -> Integrations.

Usage:
    export DISCOLIKE_API_KEY="dl_..."
    python examples/discover_and_enrich.py \
        --icp "Cybersecurity for SMBs, managed IT services" \
        --country US \
        --query "What is their pricing model, and do they sell to MSPs?"
"""

from __future__ import annotations

import argparse
import json
import sys

from discolike import Discolike


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--icp", required=True, help="ICP description, e.g. 'B2B SaaS for logistics'")
    parser.add_argument("--country", action="append", help="ISO-2 country filter, repeatable (e.g. --country US)")
    parser.add_argument("--max-records", type=int, default=10, help="How many companies to discover (default: 10)")
    parser.add_argument("--query", required=True, help="DiscoGen research prompt to run over each company")
    parser.add_argument("--timeout", type=float, default=1800.0, help="DiscoGen wait timeout in seconds")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = Discolike()

    print(f"Discovering up to {args.max_records} companies for: {args.icp!r}")
    companies = client.discover(icp_text=args.icp, country=args.country, max_records=args.max_records)
    if not companies:
        sys.exit("No companies found for that ICP - try broadening it.")
    domains = [company.domain for company in companies if company.domain]
    for company in companies:
        print(f"  {company.domain}  {company.name or ''}  (similarity {company.similarity})")

    print(f"\nRunning DiscoGen over {len(domains)} domains: {args.query!r}")
    job = client.discogen.process(query=args.query, domains=domains, web_search=True)
    status = job.wait(timeout=args.timeout, on_poll=lambda s: print(f"  status={s.status} progress={s.progress}%"))

    print("\nEnriched results:")
    for row in status.results or []:
        print(json.dumps(row, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
