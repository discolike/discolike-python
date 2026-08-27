"""Match a CSV of CRM contacts to DiscoLike persona IDs via bulk-match.

Reads contacts from a CSV (column names are configurable), submits them to
``client.contacts.bulk_match(BulkContactMatchRequest(...))`` in chunks, and writes an output CSV with the
matched ``persona_id`` and ``match_score`` per row.

Lessons baked in from production runs:

- **Two domain keys beat one.** For every row we derive a domain from BOTH the
  website column AND the email address (skipping free-mail providers such as
  gmail.com), submit a query per key, and keep the best-scoring hit. This
  measurably improves the match rate on messy CRM exports.
- **Resumable checkpointing.** Every completed chunk is appended to a JSONL
  checkpoint, so an interrupted run picks up where it left off. On a chunk
  failure or timeout the rows are deliberately NOT checkpointed as no-match --
  they stay pending, so simply rerunning the script retries them.

Country values must be ISO-3166-1 alpha-2 codes (e.g. "US", "DE"); anything
else is omitted, because ``person_country`` is a hard filter server-side.

Usage:
    export DISCOLIKE_API_KEY="dl_..."
    python examples/match_crm_contacts.py contacts.csv --output matched.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from discolike import Discolike
from discolike.requests import BulkContactMatchRequest

MAX_QUERIES_PER_CALL = 500  # bulk_match accepts 1-500 queries per request

FREE_MAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "yahoo.co.uk",
        "hotmail.com",
        "hotmail.co.uk",
        "outlook.com",
        "live.com",
        "msn.com",
        "aol.com",
        "icloud.com",
        "me.com",
        "gmx.com",
        "gmx.de",
        "proton.me",
        "protonmail.com",
        "web.de",
        "mail.com",
    }
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", type=Path, help="Input CSV of CRM contacts")
    parser.add_argument("--output", type=Path, default=Path("matched.csv"), help="Output CSV path")
    parser.add_argument(
        "--checkpoint", type=Path, default=None, help="Checkpoint JSONL path (default: <output>.checkpoint.jsonl)"
    )
    parser.add_argument("--name-column", default="name", help="Full-name column (default: name)")
    parser.add_argument("--email-column", default="email", help="Email column (default: email)")
    parser.add_argument("--website-column", default="website", help="Website/domain column (default: website)")
    parser.add_argument("--country-column", default="country", help="ISO-2 country column (default: country)")
    parser.add_argument("--company-column", default="company", help="Company-name column, a soft matching signal")
    parser.add_argument("--chunk-size", type=int, default=MAX_QUERIES_PER_CALL, help="Queries per bulk-match call")
    parser.add_argument("--timeout", type=float, default=1800.0, help="Per-chunk wait timeout in seconds")
    return parser.parse_args()


def website_domain(value: str) -> str | None:
    """'https://www.example.com/about' -> 'example.com'."""
    value = value.strip()
    if not value:
        return None
    if "//" not in value:
        value = "//" + value
    host = (urlparse(value).netloc or urlparse(value).path).lower().split("/")[0].strip()
    return host.removeprefix("www.") or None


def email_domain(value: str) -> str | None:
    """'jane@acme.com' -> 'acme.com', skipping free-mail providers."""
    value = value.strip().lower()
    if "@" not in value:
        return None
    host = value.rsplit("@", 1)[1].strip().strip(".").removeprefix("www.")
    if not host or host in FREE_MAIL_DOMAINS:
        return None
    return host


def build_queries(row_id: int, row: dict[str, str], args: argparse.Namespace) -> list[dict[str, Any]]:
    """One query per distinct domain key (website + email domain), tagged with the row id.

    The ``input:row`` key is echoed back untouched in each result's ``query``,
    which is how results are joined back to input rows.
    """
    name = row.get(args.name_column, "").strip()
    email = row.get(args.email_column, "").strip()
    if not name and not email:
        return []  # bulk-match needs at least a name or an email

    base: dict[str, Any] = {"input:row": row_id}
    if name:
        base["name"] = name
    if email:
        base["email"] = email
    company = row.get(args.company_column, "").strip()
    if company:
        base["company_name"] = company
    country = row.get(args.country_column, "").strip()
    if len(country) == 2:
        base["person_country"] = country.upper()

    domains = {d for d in (website_domain(row.get(args.website_column, "")), email_domain(email)) if d}
    if not domains:
        return [base]
    return [{**base, "domain": d} for d in sorted(domains)]


def load_checkpoint(path: Path) -> dict[int, dict[str, Any] | None]:
    done: dict[int, dict[str, Any] | None] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                done[record["row"]] = record["result"]
    return done


def best_hits(results: list[Any], row_ids: list[int]) -> dict[int, dict[str, Any] | None]:
    """Union the hits across each row's queries and keep the highest-scoring one."""
    hits: dict[int, dict[str, Any] | None] = dict.fromkeys(row_ids)
    for item in results or []:
        if not isinstance(item, dict):
            continue
        row_id = (item.get("query") or {}).get("input:row")
        if row_id not in hits:
            continue
        for match in item.get("matches") or []:
            if match.get("persona_id") is None:
                continue
            score = float(match.get("match_score") or 0.0)
            current = hits[row_id]
            if current is None or score > float(current.get("match_score") or 0.0):
                hits[row_id] = {"persona_id": match["persona_id"], "match_score": score}
    return hits


def main() -> None:
    args = parse_args()
    checkpoint_path = args.checkpoint or args.output.with_suffix(".checkpoint.jsonl")

    with args.input.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    if not rows:
        sys.exit(f"No data rows found in {args.input}")

    done = load_checkpoint(checkpoint_path)
    if done:
        print(f"Resuming: {len(done)} rows already checkpointed in {checkpoint_path}")

    pending = [(i, row) for i, row in enumerate(rows) if i not in done]
    chunk_size = min(args.chunk_size, MAX_QUERIES_PER_CALL)

    # Pack rows into chunks by QUERY count, not row count: a row expands to up
    # to two queries (website domain + email domain), so chunking 500 rows at a
    # time could send up to 1,000 queries and blow the per-call limit.
    chunks: list[list[tuple[int, list[dict[str, Any]]]]] = []
    current: list[tuple[int, list[dict[str, Any]]]] = []
    query_count = 0
    for row_id, row in pending:
        row_queries = build_queries(row_id, row, args)
        if current and query_count + len(row_queries) > chunk_size:
            chunks.append(current)
            current, query_count = [], 0
        current.append((row_id, row_queries))
        query_count += len(row_queries)
    if current:
        chunks.append(current)
    print(f"{len(rows)} rows total, {len(pending)} to match now in {len(chunks)} chunk(s) of <= {chunk_size} queries")

    client = Discolike()
    failed_chunks = 0
    with checkpoint_path.open("a", encoding="utf-8") as checkpoint:
        for index, chunk in enumerate(chunks):
            queries = [query for _, row_queries in chunk for query in row_queries]
            row_ids = [row_id for row_id, _ in chunk]
            label = f"chunk {index + 1}/{len(chunks)}"
            if not queries:
                hits: dict[int, dict[str, Any] | None] = dict.fromkeys(row_ids)
            else:
                try:
                    job = client.contacts.bulk_match(
                        BulkContactMatchRequest.model_validate({"queries": queries, "limit": 1})
                    )
                    status = job.wait(timeout=args.timeout)
                except Exception as exc:  # leave the chunk un-checkpointed so a rerun retries it
                    failed_chunks += 1
                    print(f"  ! {label} failed ({exc}); rows left pending, rerun to retry")
                    continue
                hits = best_hits(status.results, row_ids)
            for row_id, result in hits.items():
                checkpoint.write(json.dumps({"row": row_id, "result": result}) + "\n")
            checkpoint.flush()
            done.update(hits)
            matched = sum(1 for value in hits.values() if value)
            print(f"  {label}: {matched}/{len(chunk)} matched")

    extra = ["persona_id", "match_score"]
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames + extra, extrasaction="ignore")
        writer.writeheader()
        for i, row in enumerate(rows):
            writer.writerow({**row, **(done.get(i) or {})})

    matched_total = sum(1 for value in done.values() if value)
    print(f"\nDone: {matched_total}/{len(rows)} matched -> {args.output}")
    if failed_chunks:
        print(f"{failed_chunks} chunk(s) failed and were not checkpointed; rerun this command to retry them.")


if __name__ == "__main__":
    main()
