"""Help-text epilogs that spell out the CLI's output contract for agents and scripts.

Every constant here is plain text (no Rich markup) so it renders identically in a
terminal, in a pipe, and in a test assertion. Response shapes mirror the SDK models in
``discolike.resources``; keep them in sync when a model changes.
"""

from __future__ import annotations

import textwrap

import typer
from typer._click import Context
from typer._click import HelpFormatter
from typer.core import TyperCommand
from typer.core import TyperGroup

from discolike._config import ENV_API_KEY
from discolike._config import config_path

EPILOG_INDENT = " "


def _echo_verbatim(epilog: str) -> None:
    # Typer's rich formatter reflows epilog paragraphs into prose, which destroys the
    # aligned tables below. Print the epilog ourselves, exactly as written.
    typer.echo(textwrap.indent(epilog.rstrip("\n"), EPILOG_INDENT))


class ContractCommand(TyperCommand):
    """A command whose epilog is printed verbatim, not reflowed."""

    def format_help(self, ctx: Context, formatter: HelpFormatter) -> None:
        epilog, self.epilog = self.epilog, None
        try:
            super().format_help(ctx, formatter)
        finally:
            self.epilog = epilog
        if epilog:
            _echo_verbatim(epilog)


class ContractGroup(TyperGroup):
    """A command group whose epilog is printed verbatim, not reflowed."""

    def format_help(self, ctx: Context, formatter: HelpFormatter) -> None:
        epilog, self.epilog = self.epilog, None
        try:
            super().format_help(ctx, formatter)
        finally:
            self.epilog = epilog
        if epilog:
            _echo_verbatim(epilog)


_CONFIG_PATH_HINT = "$XDG_CONFIG_HOME/discolike/config.json (default ~/.config/discolike/config.json)"

MAIN_EPILOG = f"""\
Output contract:
  Success      JSON on stdout, exit 0. JSON is the default whenever stdout is not a
               TTY; --format json forces it and --format table renders a table for
               humans. Progress lines from --wait go to stderr only.
  Failure      {{"error", "code", "message", "status_code", "exit_code"}} on stderr
               with a non-zero exit code. Branch on "code" (stable) or the exit code;
               "error" is the SDK exception class name. rate_limited adds "retry_after".
  Determinism  No spinners, colors, or prompts on stdout when piped.

Exit codes:
  0  success
  1  server_error, job_failed, job_timeout, or any other unrecoverable error
  2  validation_error   input rejected before or by the API (bad flag, enum, range)
  3  auth_required      no credential found: run `discolike auth login`
     auth_invalid       credential rejected (401/403); plan_access needs a higher plan
  4  rate_limited       HTTP 429; wait "retry_after" seconds, then retry
  5  network_error      could not reach the API
  6  not_found          HTTP 404

Environment:
  {ENV_API_KEY}   API key; overrides the config file written by `discolike auth login`.
  Config file          {_CONFIG_PATH_HINT}
                       (resolved now: {config_path()})

Examples:
  $ discolike count --country DE --phrase-match "managed detection" --format json | jq .count
  $ discolike discover --icp-prompt "cybersecurity for SMBs" --max-records 100 --format json | jq -r '.[].domain'
  $ discolike validate-icp --icp "sells to hospitals" --domain a.com --domain b.com --wait --format json | jq '.'
"""

_COMPANY_ROW = """\
    {"domain": <string>, "name": <string>, "similarity": <0-1>, "score": <int>,
     "description": <string>, "employees": <string>, "revenue_range": <string>,
     "address": {"city", "state", "country"}, "industry_groups": {<name>: <weight>},
     "business_model": {<name>: <weight>}, "mx_provider": <string>, ...}"""

_JOB_SUBMITTED = """\
  Without --wait:
    {"task_id": <string>, "task_family": <string>, "hint": "poll with: discolike discogen status ..."}"""

_JOB_ERRORS = """\
Common errors:
  validation_error (exit 2)  bad flag value, empty domain list, or an unknown --model.
  auth_required    (exit 3)  no credential; run `discolike auth login`.
  plan_access      (exit 3)  the plan does not include this job type.
  job_failed       (exit 1)  the job finished with an error (only with --wait).
  job_timeout      (exit 1)  --timeout elapsed before the job finished; poll with `discolike discogen status`."""

_SEARCH_ERRORS = """\
Common errors:
  validation_error (exit 2)  unknown filter value, bad range, or more than 10 seed domains.
  auth_required    (exit 3)  no credential; run `discolike auth login`.
  plan_access      (exit 3)  the plan does not allow this filter or record count.
  rate_limited     (exit 4)  HTTP 429; retry after "retry_after" seconds."""

COMMAND_EPILOGS: dict[str, str] = {
    "discover": f"""\
Output (success, exit 0):
  [
{_COMPANY_ROW}
  ]
  One row per matched company, ranked by similarity. Billed per 1,000 new records;
  records seen in the last 90 days are free. Count first: `discolike count` is free.

{_SEARCH_ERRORS}
""",
    "count": f"""\
Output (success, exit 0):
  {{"count": <int>}}
  Free. Same filters as `discover`; run it before any large pull.

{_SEARCH_ERRORS}
""",
    "match": """\
Output (success, exit 0):
  Single (--name):
    {"query": {"name", "country", "state", "city", "zip", "phones"},
     "matches": [{"domain": <string>, "name": <string>, "match_confidence": <0-100>, ...}]}
  Bulk (--file) without --wait:
    {"task_id": <string>, "task_family": <string>, "hint": <string>}
  Bulk with --wait: one row per input row; rows the backend could not process carry
  "match_error": "search_failed", which is not the same as no match.

Common errors:
  validation_error (exit 2)  neither --name nor --file given, or a named column is missing.
  auth_required    (exit 3)  no credential; run `discolike auth login`.
  job_timeout      (exit 1)  --timeout elapsed on a bulk match; poll with `discolike discogen status`.
""",
    "append": """\
Output (success, exit 0):
  JSON (default): [{"domain": <string>, <dataset fields>...}] one row per input row.
  --csv --output FILE: {"written": <path>, "bytes": <int>} and the CSV is on disk.
  Datasets: bizdata, domain_status, redirects, growth, vendors, subdomains.
  Up to 10,000 rows per request; billed per new company record.

Common errors:
  validation_error (exit 2)  missing --domain-column, unknown --dataset, or --csv without --output.
  auth_required    (exit 3)  no credential; run `discolike auth login`.
  plan_access      (exit 3)  a requested dataset is not on the plan.
""",
    "validate-icp": f"""\
Output (success, exit 0):
{_JOB_SUBMITTED}
  With --wait: the results object keyed by domain:
    {{<domain>: {{"Fit": "yes"|"no", "Confidence": "high"|"medium"|"low", "Reasoning": <string>}}, ...}}
  Runs on the account's own LLM provider key.
  With --integration-id native-icp: DiscoLike's own ICP-fit model, no LLM key or cost and no
  web search. Keys become "ICP Fit" ("Yes"|"No" at a 0.50 threshold on the score), "ICP Score"
  (the calibrated probability, 0.00-1.00 as a string) and "Reasoning", always null there: the
  model returns a score, not an explanation. A 400 when the ICP text yields no Mandatory /
  Reject if / Nice-to-have prompt, a 503 when no ICP-fit engine is available.

{_JOB_ERRORS}
""",
    "segment": f"""\
Output (success, exit 0):
{_JOB_SUBMITTED}
  With --wait: one BizData row per active domain, plus its cluster:
    [{{"domain", "name", "score", "segment_id": <int, -1 = unclustered>,
      "segment_description": <string>, "probability": <0-1>, ...}}]
  Closed or unindexed input domains are omitted.

{_JOB_ERRORS}
""",
    "extract": """\
Output (success, exit 0):
  {"text": <string>, "language": <ISO 639-1>}
  Fetches the page live; use it to confirm a seed domain is the right company.

Common errors:
  validation_error (exit 2)  neither a URL argument nor --domain given.
  auth_required    (exit 3)  no credential; run `discolike auth login`.
  not_found        (exit 6)  the page could not be fetched.
""",
    "signup": """\
Output (success, exit 0):
  {"status": <string>, "email": <string>, "org_domain": <string>,
   "org_status": <string>, "next_step": <string>}
  No credential is returned. Relay "next_step" to the person: they confirm by email,
  log in, pick a plan, then run `discolike auth login`. No login is needed for this call.

Common errors:
  validation_error (exit 2)  free-mail or disposable email domain, or a missing name.
  error            (exit 1)  HTTP 409: the account already exists; send them to log in.
""",
    "contacts search": """\
Output (success, exit 0):
  [{"persona_id": <int>, "domain": <string>, "name": <string>, "title": <string>,
    "email": <string>, ...}]
  Billed per new contact record. `discolike contacts count` with the same filters is free.

Common errors:
  validation_error (exit 2)  unknown seniority/department value or a bad range.
  auth_required    (exit 3)  no credential; run `discolike auth login`.
  plan_access      (exit 3)  contacts are not included on the plan.
""",
    "contacts generate": f"""\
Output (success, exit 0):
{_JOB_SUBMITTED}
  With --wait: results keyed by domain, zero or more candidate rows each:
    {{<domain>: [{{"name", "title", "department", "seniority", "email", "linkedin_url",
      "skills", "phone": [{{"phone", "type"}}], "email_pattern", "email_pattern_confidence",
      "email_pattern_guess"}}], ...}}
  Rows are candidates; email is set only when publicly verifiable.
  Runs live web search on the account's own LLM and search provider keys; no platform billing.

{_JOB_ERRORS}
""",
    "discogen run": f"""\
Output (success, exit 0):
{_JOB_SUBMITTED}
  With --wait: one entry per domain with the model's structured answer to --query.
  Send the whole list in one call; parallel jobs share the provider key and rate-limit each other.

{_JOB_ERRORS}
""",
    "discogen status": """\
Output (success, exit 0):
  {"status": "pending"|"running"|"completed"|"failed", "progress": <0-100>,
   "results": <any>, "warnings": [<string>], "estimated_cost": <float>,
   "cost_metadata": {<provider/model>: {...}, "search_provider": {...}}}
  "results" is null until the job completes. Pass --family for non-DiscoGen jobs.

Common errors:
  validation_error (exit 2)  unknown --family value.
  auth_required    (exit 3)  no credential; run `discolike auth login`.
  not_found        (exit 6)  no job with that task id in that family.
""",
    "queries create-exclusion-list": """\
Output (success, exit 0):
  {"query_id": <string>, "query_name": <string>, "action": <string>,
   "domain_count": <int>, "persona_id_count": <int>, "row_count": <int>, "tags": [<string>]}
  Pass "query_id" as --exclusion-query-id (or --inclusion-query-id) on the next discover.
  Minimum 20 domains; lists hold up to 250,000 domains on every plan.

Common errors:
  validation_error (exit 2)  fewer than 20 domains, or a missing --name.
  auth_required    (exit 3)  no credential; run `discolike auth login`.
""",
    "auth login": """\
Output (success, exit 0):
  Browser (default): {"logged_in": true, "method": "oauth", "expires_at": <ISO 8601>}
  --api-key KEY:     {"logged_in": true, "source": "api_key"}
  The credential is saved to the config file; later commands read it automatically.
  Progress lines (the URL to open, browser wait) go to stderr; only the JSON above is on stdout.
  Headless: --no-browser prints the URL to open; --port pins the loopback port for SSH.

Common errors:
  auth_invalid     (exit 3)  the API key was rejected.
  error            (exit 1)  {"error": "LoginError", ...}: timeout, denied consent, or state mismatch.
""",
    "auth status": """\
Output (success, exit 0):
  API key: {"source": "option"|"env"|"config", "method": "api_key", "api_key": <masked>, "valid": true}
  OAuth:   {"source": "config", "method": "oauth", "expires_at": <ISO 8601>, "expired": <bool>, "valid": true}
  Exit 0 here is the whole proof that the CLI is signed in.

Common errors:
  auth_required    (exit 3)  no credential anywhere; run `discolike auth login`.
  auth_invalid     (exit 3)  the stored credential no longer verifies; log in again.
""",
    "account usage": """\
Output (success, exit 0):
  {"requests_mtd": <int>, "records_mtd": <int>, "spend_mtd": <float>}
  Month-to-date. Report it before any paid flow so the person knows the baseline.

Common errors:
  auth_required    (exit 3)  no credential; run `discolike auth login`.
""",
}


def epilog(name: str) -> str:
    return COMMAND_EPILOGS[name]
