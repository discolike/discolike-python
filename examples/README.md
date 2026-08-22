# Examples

Runnable, self-contained scripts showing how to use the DiscoLike Python SDK for common GTM workflows: matching a messy CRM export to DiscoLike contacts, finding verified work emails in bulk, and discovering plus AI-enriching target accounts. Each script is stdlib-plus-SDK only, has an argparse CLI, and is meant to be copied into your own pipeline and adapted.

| Script | What it does |
|---|---|
| [`match_crm_contacts.py`](match_crm_contacts.py) | Match a CSV of CRM contacts to DiscoLike persona IDs via `contacts.bulk_match()`, with dual domain keys (website + email domain), resumable JSONL checkpointing, and a persona_id + match_score output CSV |
| [`find_emails_from_csv.py`](find_emails_from_csv.py) | Find work emails for a CSV of people (first name, last name, domain) via `email.find_batch()` in chunks of 500; only status "found" bills |
| [`discover_and_enrich.py`](discover_and_enrich.py) | Discover companies matching an ICP with `client.discover()`, then run a DiscoGen research prompt over them with `discogen.process()` and `job.wait()` |

## Running

```bash
pip install discolike
export DISCOLIKE_API_KEY="dl_..."   # create one at https://app.discolike.com/account/management/keys
python examples/<script>.py --help
```
