# Cookbook

Runnable scripts for common GTM workflows on the [DiscoLike API](https://discolike.com/api/), written against the [Python SDK](https://docs.discolike.com/sdk/). Each one is stdlib plus `discolike`, takes its inputs on the command line, and reads your key from `DISCOLIKE_API_KEY`.

```bash
pip install "discolike[cli]"
export DISCOLIKE_API_KEY="dl_..."   # create one at https://app.discolike.com/account/management/keys
```

| Script | What it does | How to run |
|---|---|---|
| [`tam_from_seed_domains.py`](tam_from_seed_domains.py) | Counts companies in a country and employee bucket, then discovers lookalikes of three seed domains and writes them to CSV | `python examples/tam_from_seed_domains.py stripe.com adyen.com checkout.com US 51,200 --max-records 100 --output tam.csv` |
| [`icp_prompt_search.py`](icp_prompt_search.py) | Turns a plain-English ICP into a company list with similarity scores | `python examples/icp_prompt_search.py "Series A fintechs in Europe selling to SMBs" --country EU` |
| [`phrase_match_count.py`](phrase_match_count.py) | Counts sites whose text contains an exact phrase, then lists them | `python examples/phrase_match_count.py "SOC 2" --country US` |
| [`enrich_crm_export.py`](enrich_crm_export.py) | Adds firmographics (size, revenue, location, industry, business model) to every domain in a CSV | `python examples/enrich_crm_export.py accounts.csv --domain-column website --output enriched.csv` |
| [`contacts_at_results.py`](contacts_at_results.py) | Discovers companies for an ICP, then finds contacts at the top N filtered by seniority, department, or title | `python examples/contacts_at_results.py "B2B SaaS selling to sales teams" --top 10 --seniority executive --has-email` |
| [`agent_signup_to_first_search.py`](agent_signup_to_first_search.py) | Opens a DiscoLike account for a person from an agent, relays `next_step`, and runs a first search once `DISCOLIKE_API_KEY` is set | `python examples/agent_signup_to_first_search.py --email jane@acme.com --first-name Jane --last-name Doe` |
| [`discover_and_enrich.py`](discover_and_enrich.py) | Discovers companies for an ICP, then runs a DiscoGen research prompt over them (needs a BYOK LLM provider) | `python examples/discover_and_enrich.py --icp "Cybersecurity for SMBs" --country US --query "What is their pricing model?"` |
| [`find_emails_from_csv.py`](find_emails_from_csv.py) | Finds verified work emails for a CSV of first name, last name, domain in batches of 500; only status `found` bills | `python examples/find_emails_from_csv.py people.csv --output emails.csv` |
| [`match_crm_contacts.py`](match_crm_contacts.py) | Matches a messy CRM contact export to DiscoLike persona IDs with resumable checkpointing | `python examples/match_crm_contacts.py contacts.csv --output matched.csv` |
| [`cli_recipes.sh`](cli_recipes.sh) | The same searches as `discolike discover`, `discolike count`, `discolike contacts search`, and `discolike signup` one-liners | `bash examples/cli_recipes.sh` |

Every script prints `--help`. Employee ranges are `min,max` strings such as `51,200`; countries are ISO-2 codes or region aliases like `EU`, `DACH`, `APAC`.
