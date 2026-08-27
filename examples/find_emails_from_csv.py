"""Find work email addresses for a CSV of people via the email finder batch API.

Reads people from a CSV with ``first_name``, ``last_name``, and ``domain``
columns (names configurable), submits them with
``client.email.find_batch(FindEmailBatchRequest(...))`` in chunks of up to 500, waits for
each batch with ``batch.results()``, and writes the found emails plus status
to an output CSV.

Billing note: only results with status "found" (an SMTP-verified address) are
billed. Catch-all domains and pattern-based guesses are returned for free.

Usage:
    export DISCOLIKE_API_KEY="dl_..."
    python examples/find_emails_from_csv.py people.csv --output emails.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from discolike import Discolike
from discolike import EnumerationOutput
from discolike.requests import FindEmailBatchRequest

MAX_CONTACTS_PER_BATCH = 500

OUTPUT_FIELDS = ["first_name", "last_name", "domain", "email", "status", "is_catch_all", "error"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", type=Path, help="Input CSV of people")
    parser.add_argument("--output", type=Path, default=Path("emails.csv"), help="Output CSV path")
    parser.add_argument("--first-name-column", default="first_name", help="First-name column (default: first_name)")
    parser.add_argument("--last-name-column", default="last_name", help="Last-name column (default: last_name)")
    parser.add_argument("--domain-column", default="domain", help="Company-domain column (default: domain)")
    parser.add_argument("--timeout", type=float, default=1800.0, help="Per-batch wait timeout in seconds")
    return parser.parse_args()


def load_contacts(path: Path, args: argparse.Namespace) -> list[dict[str, str]]:
    contacts: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            first = row.get(args.first_name_column, "").strip()
            last = row.get(args.last_name_column, "").strip()
            domain = row.get(args.domain_column, "").strip().lower().removeprefix("www.")
            if first and last and domain:
                contacts.append({"first_name": first, "last_name": last, "domain": domain})
    return contacts


def main() -> None:
    args = parse_args()
    contacts = load_contacts(args.input, args)
    if not contacts:
        sys.exit(f"No usable rows (first name + last name + domain) found in {args.input}")

    client = Discolike()
    found = 0
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for start in range(0, len(contacts), MAX_CONTACTS_PER_BATCH):
            chunk = contacts[start : start + MAX_CONTACTS_PER_BATCH]
            print(f"Submitting batch of {len(chunk)} contacts ({start + len(chunk)}/{len(contacts)})...")
            batch = client.email.find_batch(FindEmailBatchRequest.model_validate({"requests": chunk}))
            results = batch.results(timeout=args.timeout)
            for item in results.results:
                output = item.result
                if not isinstance(output, EnumerationOutput):
                    # Failed jobs carry no EnumerationOutput (so no identity),
                    # but must not vanish from the output: keep the status and
                    # error so the failure is visible and countable.
                    writer.writerow(
                        {
                            "first_name": "",
                            "last_name": "",
                            "domain": "",
                            "email": "",
                            "status": item.status or "failed",
                            "is_catch_all": "",
                            "error": item.error or "",
                        }
                    )
                    continue
                email = output.result.email if output.result is not None else None
                if output.status == "found":
                    found += 1
                writer.writerow(
                    {
                        "first_name": output.first_name,
                        "last_name": output.last_name,
                        "domain": output.domain,
                        "email": email or "",
                        "status": output.status or "",
                        "is_catch_all": output.is_catch_all,
                        "error": output.error or "",
                    }
                )
            handle.flush()

    print(f'\nDone: {found}/{len(contacts)} verified emails (status "found") -> {args.output}')


if __name__ == "__main__":
    main()
