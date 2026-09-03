#!/usr/bin/env bash
# The same searches as the Python scripts, as `discolike` CLI one-liners.
# Install: pip install discolike-cli   Auth: export DISCOLIKE_API_KEY="dl_..." or `discolike auth login`
set -euo pipefail

# tam_from_seed_domains.py: count the country + size bucket, then discover lookalikes of three seed domains
discolike count --country US --employee-range 51,200 --format json
discolike discover --domain stripe.com --domain adyen.com --domain checkout.com \
  --country US --employee-range 51,200 --max-records 100 --format json

# icp_prompt_search.py: natural-language ICP, domain + name + similarity
discolike discover --icp-prompt "Series A fintechs in Europe selling to SMBs" --country EU --max-records 25 --format json \
  | jq -r '.[] | [.domain, .name, .similarity] | @tsv'

# phrase_match_count.py: sites whose text contains an exact phrase, count then list
discolike count --phrase-match "SOC 2" --country US --format json
discolike discover --phrase-match "SOC 2" --country US --max-records 50 --format json | jq -r '.[].domain'

# contacts_at_results.py: discover companies, then executives at the first ten of them
discolike discover --icp-prompt "B2B SaaS companies selling to sales teams" --max-records 10 --format json \
  | jq -r '.[].domain' \
  | xargs -I{} printf -- '--domain %s ' {} \
  | xargs discolike contacts search --seniority executive --has-email --format json

# enrich_crm_export.py: one company profile by domain
discolike company data stripe.com --format json

# agent_signup_to_first_search.py: open an account for a person, no auth needed
discolike signup --email jane@acme.com --first-name Jane --last-name Doe --agent cookbook
