"""Complete minimal REST prospecting responses shared by SDK and CLI tests."""

from typing import Any

RUN_ID = "00000000-0000-0000-0000-000000000001"
CREATED_AT = "2026-09-26T12:00:00Z"


def run_payload(status: str = "drafting") -> dict[str, Any]:
    return {
        "run_id": RUN_ID,
        "status": status,
        "max_actions": 30,
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
        "brief": {"brief": "US logistics companies and operations leaders"},
        "target_companies": 25,
        "contacts_per_company": 2,
        "companies": [{"domain": "example.com"}],
    }


def message_payload() -> dict[str, Any]:
    return {"seq": 8, "created_at": CREATED_AT, "role": "user", "kind": "text", "content": "Make it 100 companies"}


def summary_payload() -> dict[str, Any]:
    return {key: value for key, value in run_payload().items() if key not in {"max_actions", "companies", "brief"}} | {
        "brief": "US logistics companies and operations leaders"
    }
