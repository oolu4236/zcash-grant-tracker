"""
Scrape grant financial data from OpenZcash API.
Source: openzcash.org/api/zcg
Updates every 6 hours from the official ZCG Google Sheet.
"""

import urllib.request
import json
import os
from datetime import datetime, timezone

API_BASE = "https://openzcash.org/api/zcg"


def fetch_json(endpoint):
    """Fetch JSON from OpenZcash API."""
    url = f"{API_BASE}/{endpoint}" if not endpoint.startswith("http") else endpoint
    print(f"  Fetching {url}...")
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "zcash-grant-tracker",
    })
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def fetch_grants():
    """Fetch all grants with financial data."""
    return fetch_json("data/grants")


def fetch_disbursements():
    """Fetch full payment ledger."""
    return fetch_json("data/disbursements")


def fetch_recipients():
    """Fetch per-recipient budget summaries."""
    return fetch_json("data/recipients")


def fetch_coinholder_rounds():
    """Fetch CDRGP rounds with proposals and outcomes."""
    return fetch_json("coinholder/round")


def fetch_current_proposals():
    """Fetch current CDRGP submissions."""
    url = "https://openzcash.org/api/coinholders/proposals"
    print(f"  Fetching {url}...")
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "zcash-grant-tracker",
    })
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def scrape_financials():
    """Main scraper: pull all financial data."""
    print("Fetching OpenZcash financial data...")

    data = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        grants = fetch_grants()
        data["grants"] = grants
        print(f"  Grants: {len(grants) if isinstance(grants, list) else 'object'}")
    except Exception as e:
        print(f"  Error fetching grants: {e}")
        data["grants"] = None

    try:
        disbursements = fetch_disbursements()
        data["disbursements"] = disbursements
        count = len(disbursements) if isinstance(disbursements, list) else "object"
        print(f"  Disbursements: {count}")
    except Exception as e:
        print(f"  Error fetching disbursements: {e}")
        data["disbursements"] = None

    try:
        recipients = fetch_recipients()
        data["recipients"] = recipients
        count = len(recipients) if isinstance(recipients, list) else "object"
        print(f"  Recipients: {count}")
    except Exception as e:
        print(f"  Error fetching recipients: {e}")
        data["recipients"] = None

    try:
        coinholder = fetch_coinholder_rounds()
        data["coinholder_rounds"] = coinholder
        print(f"  Coinholder rounds: fetched")
    except Exception as e:
        print(f"  Error fetching coinholder rounds: {e}")
        data["coinholder_rounds"] = None

    return data


def save_financials(data, output_path="data/financials.json"):
    """Save financial data to JSON."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved financials to {output_path}")


if __name__ == "__main__":
    data = scrape_financials()
    save_financials(data)

    # Summary
    if data.get("grants") and isinstance(data["grants"], list):
        total_usd = sum(
            g.get("total_budget", 0) or 0
            for g in data["grants"]
            if isinstance(g, dict)
        )
        print(f"\nTotal budget across all grants: ${total_usd:,.0f}")
