"""
Scrape ZCG grant issues from GitHub API.
Collects: issue metadata, labels (lifecycle state), timeline events (label changes),
milestone data, and linked repos for activity cross-referencing.
"""

import urllib.request
import json
import os
import time
from datetime import datetime, timezone

REPO = "ZcashCommunityGrants/zcashcommunitygrants"
API_BASE = "https://api.github.com"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# Grant lifecycle labels — order matters for status derivation
LIFECYCLE_LABELS = [
    "✔️ Grant Complete",
    "❌ Grant Cancelled Before Completion",
    "⏰ Milestones Past Due",
    "✔️ Milestone Payment Complete",
    "✅ Milestone Payment Approved",
    "✅ Startup Payment Completed",
    "✅ KYC Verified",
    "🔐 KYC Required",
    "✅ Grant Approved",
    "👀 Ready For ZCG Review",
    "📋 Grant Application",
    "❌ Grant Declined",
    "⛔ Does Not Meet Criteria",
    "Closed - Did Not Follow Process",
    "Grant Withdrawn by Submitter",
]

MILESTONE_LABELS = [f"🎯 Milestone {i} Complete" for i in range(1, 22)]


def gh_request(url, headers=None):
    """Make authenticated GitHub API request with rate limit handling."""
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "zcash-grant-tracker",
    }
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    if headers:
        h.update(headers)

    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req) as resp:
            # Check rate limit
            remaining = resp.headers.get("X-RateLimit-Remaining", "999")
            if int(remaining) < 10:
                reset_ts = int(resp.headers.get("X-RateLimit-Reset", "0"))
                wait = max(0, reset_ts - int(time.time())) + 1
                print(f"  Rate limit low ({remaining} remaining), waiting {wait}s...")
                time.sleep(wait)
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {url}")
        if e.code == 403:
            reset_ts = int(e.headers.get("X-RateLimit-Reset", "0"))
            wait = max(0, reset_ts - int(time.time())) + 2
            print(f"  Rate limited. Waiting {wait}s...")
            time.sleep(wait)
            return gh_request(url, headers)
        raise


def fetch_all_issues():
    """Fetch all issues (grant applications) with pagination."""
    issues = []
    page = 1
    while True:
        url = (
            f"{API_BASE}/repos/{REPO}/issues"
            f"?state=all&per_page=100&page={page}&sort=created&direction=desc"
        )
        print(f"  Fetching issues page {page}...")
        batch = gh_request(url)
        if not batch:
            break
        # Filter out pull requests
        batch = [i for i in batch if "pull_request" not in i]
        issues.extend(batch)
        if len(batch) < 100:
            break
        page += 1
        time.sleep(0.5)
    return issues


def fetch_issue_events(issue_number):
    """Fetch timeline events for an issue (label changes, etc)."""
    events = []
    page = 1
    while True:
        url = (
            f"{API_BASE}/repos/{REPO}/issues/{issue_number}/events"
            f"?per_page=100&page={page}"
        )
        batch = gh_request(url)
        if not batch:
            break
        events.extend(batch)
        if len(batch) < 100:
            break
        page += 1
        time.sleep(0.3)
    return events


def derive_status(labels):
    """Derive current grant status from labels."""
    label_names = {l["name"] for l in labels}

    if "✔️ Grant Complete" in label_names:
        return "complete"
    if "❌ Grant Cancelled Before Completion" in label_names:
        return "cancelled"
    if "Grant Withdrawn by Submitter" in label_names:
        return "withdrawn"
    if "❌ Grant Declined" in label_names:
        return "declined"
    if "⛔ Does Not Meet Criteria" in label_names:
        return "rejected"
    if "Closed - Did Not Follow Process" in label_names:
        return "process_failure"
    if "⏰ Milestones Past Due" in label_names:
        return "overdue"
    if "✔️ Milestone Payment Complete" in label_names or "✅ Milestone Payment Approved" in label_names:
        return "in_progress"
    if "✅ Startup Payment Completed" in label_names:
        return "started"
    if "✅ Grant Approved" in label_names:
        return "approved"
    if "👀 Ready For ZCG Review" in label_names:
        return "under_review"
    if "📋 Grant Application" in label_names:
        return "applied"
    return "unknown"


def count_completed_milestones(labels):
    """Count how many milestone labels are present."""
    label_names = {l["name"] for l in labels}
    return sum(1 for ml in MILESTONE_LABELS if ml in label_names)


def extract_grant_amount(body):
    """Try to extract requested USD amount from issue body."""
    if not body:
        return None
    import re
    # Look for dollar amounts near "Requested" or "Total Budget"
    patterns = [
        r'Requested Grant Amount.*?\$?([\d,]+(?:\.\d{2})?)',
        r'Total Budget.*?\$?([\d,]+(?:\.\d{2})?)',
        r'Total \$\(USD\):\s*\$?([\d,]+(?:\.\d{2})?)',
    ]
    for pattern in patterns:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(",", "")
            try:
                return float(amount_str)
            except ValueError:
                continue
    return None


def extract_category(body):
    """Try to extract category from issue body."""
    if not body:
        return None
    import re
    match = re.search(r'### Category\s*\n\s*(\w[\w\s&/]*)', body)
    if match:
        return match.group(1).strip()
    return None


def parse_issue(issue):
    """Parse a GitHub issue into a structured grant record."""
    labels = issue.get("labels", [])
    body = issue.get("body", "") or ""

    return {
        "issue_number": issue["number"],
        "title": issue["title"],
        "author": issue["user"]["login"] if issue.get("user") else None,
        "created_at": issue["created_at"],
        "updated_at": issue["updated_at"],
        "closed_at": issue.get("closed_at"),
        "state": issue["state"],
        "status": derive_status(labels),
        "labels": [l["name"] for l in labels],
        "milestones_completed": count_completed_milestones(labels),
        "requested_amount": extract_grant_amount(body),
        "category": extract_category(body),
        "url": issue["html_url"],
        "comments_count": issue.get("comments", 0),
    }


def build_timeline(events):
    """Extract label-change timeline from issue events."""
    timeline = []
    for event in events:
        if event.get("event") == "labeled":
            label_name = event.get("label", {}).get("name", "")
            if label_name in LIFECYCLE_LABELS or label_name in MILESTONE_LABELS:
                timeline.append({
                    "event": "labeled",
                    "label": label_name,
                    "date": event["created_at"],
                    "actor": event.get("actor", {}).get("login"),
                })
        elif event.get("event") == "unlabeled":
            label_name = event.get("label", {}).get("name", "")
            if label_name in LIFECYCLE_LABELS or label_name in MILESTONE_LABELS:
                timeline.append({
                    "event": "unlabeled",
                    "label": label_name,
                    "date": event["created_at"],
                    "actor": event.get("actor", {}).get("login"),
                })
    return timeline


def scrape_grants(fetch_events_for_approved=True):
    """Main scraper: fetch all grants, optionally with timelines for approved ones."""
    print("Fetching all grant issues...")
    issues = fetch_all_issues()
    print(f"  Found {len(issues)} issues.")

    grants = []
    for issue in issues:
        grant = parse_issue(issue)
        grants.append(grant)

    # Fetch events for approved/active/complete grants (the ones we care about tracking)
    if fetch_events_for_approved:
        trackable_statuses = {
            "approved", "started", "in_progress", "overdue",
            "complete", "cancelled",
        }
        trackable = [g for g in grants if g["status"] in trackable_statuses]
        print(f"Fetching timelines for {len(trackable)} trackable grants...")

        for i, grant in enumerate(trackable):
            print(f"  [{i+1}/{len(trackable)}] #{grant['issue_number']} — {grant['title'][:50]}...")
            events = fetch_issue_events(grant["issue_number"])
            grant["timeline"] = build_timeline(events)
            time.sleep(0.3)

    return grants


def save_grants(grants, output_path="data/grants.json"):
    """Save grants data to JSON."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "total_issues": len(grants),
            "grants": grants,
        }, f, indent=2)
    print(f"Saved {len(grants)} grants to {output_path}")


if __name__ == "__main__":
    grants = scrape_grants()
    save_grants(grants)

    # Summary stats
    statuses = {}
    for g in grants:
        statuses[g["status"]] = statuses.get(g["status"], 0) + 1
    print("\nStatus breakdown:")
    for status, count in sorted(statuses.items(), key=lambda x: -x[1]):
        print(f"  {status}: {count}")
