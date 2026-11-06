"""
Grant health analysis engine.
Combines data from all scrapers to produce a grant health assessment.
Optionally uses Claude API for editorial analysis of meeting minutes.
"""

import json
import os
from datetime import datetime, timezone, timedelta


def load_data():
    """Load all scraped data."""
    data = {}

    for name, path in [
        ("github", "data/grants.json"),
        ("financials", "data/financials.json"),
        ("minutes", "data/meeting_minutes.json"),
    ]:
        if os.path.exists(path):
            with open(path) as f:
                data[name] = json.load(f)
        else:
            print(f"  Warning: {path} not found")
            data[name] = None

    return data


def analyze_delivery_rate(financials):
    """Calculate delivery metrics from OpenZcash data."""
    if not financials or not financials.get("grants"):
        return None

    grants = financials["grants"]["data"]
    total_grants = len(grants)

    # Status breakdown
    statuses = {}
    for g in grants:
        s = g.get("status", "unknown")
        statuses[s] = statuses.get(s, 0) + 1

    # Milestone delivery rate
    total_milestones = sum(g.get("milestones", 0) for g in grants)
    paid_milestones = sum(g.get("milestonesPaid", 0) for g in grants)
    milestone_rate = (paid_milestones / total_milestones * 100) if total_milestones > 0 else 0

    # Financial totals
    total_usd = sum(g.get("usd", 0) or 0 for g in grants)
    total_zec = sum(g.get("zec", 0) or 0 for g in grants)

    # Category breakdown
    categories = {}
    for g in grants:
        cat = g.get("category", "Unknown")
        if cat not in categories:
            categories[cat] = {"count": 0, "usd": 0}
        categories[cat]["count"] += 1
        categories[cat]["usd"] += g.get("usd", 0) or 0

    return {
        "total_grants": total_grants,
        "status_breakdown": statuses,
        "total_milestones": total_milestones,
        "paid_milestones": paid_milestones,
        "milestone_delivery_rate": round(milestone_rate, 1),
        "total_usd_committed": round(total_usd, 2),
        "total_zec_disbursed": round(total_zec, 2),
        "category_breakdown": categories,
    }


def find_stalled_grants(financials, days_threshold=60):
    """Find grants that appear stalled — open but no recent payment."""
    if not financials or not financials.get("grants"):
        return []

    grants = financials["grants"]["data"]
    now = datetime.now(timezone.utc)
    stalled = []

    for g in grants:
        if g.get("status") != "open":
            continue

        milestones = g.get("milestones", 0) or 0
        paid = g.get("milestonesPaid", 0) or 0

        if milestones == 0:
            continue

        # Check last payment date
        last_paid = g.get("lastPaid")
        if last_paid:
            try:
                last_date = datetime.fromisoformat(last_paid + "T00:00:00+00:00")
                days_since = (now - last_date).days
                if days_since > days_threshold and paid < milestones:
                    stalled.append({
                        "grant": g["grant"],
                        "grantee": g.get("grantee", "Unknown"),
                        "usd": g.get("usd", 0),
                        "milestones": milestones,
                        "milestones_paid": paid,
                        "last_paid": last_paid,
                        "days_since_payment": days_since,
                        "completion_pct": round(paid / milestones * 100, 1) if milestones > 0 else 0,
                    })
            except (ValueError, TypeError):
                pass

        # Grant approved but never paid
        elif paid == 0:
            first_paid = g.get("firstPaid")
            if not first_paid:
                stalled.append({
                    "grant": g["grant"],
                    "grantee": g.get("grantee", "Unknown"),
                    "usd": g.get("usd", 0),
                    "milestones": milestones,
                    "milestones_paid": 0,
                    "last_paid": None,
                    "days_since_payment": None,
                    "completion_pct": 0,
                    "note": "approved but never paid",
                })

    # Sort by days since payment (most stalled first)
    stalled.sort(key=lambda x: x.get("days_since_payment") or 9999, reverse=True)
    return stalled


def find_recently_completed(financials, days=30):
    """Find grants completed in the last N days."""
    if not financials or not financials.get("disbursements"):
        return []

    disbursements = financials["disbursements"]["data"]
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    recent = []
    for d in disbursements:
        paid_date = d.get("paidOutDate")
        if not paid_date:
            continue
        try:
            dt = datetime.fromisoformat(paid_date + "T00:00:00+00:00")
            if dt >= cutoff:
                recent.append({
                    "recipient": d.get("recipient"),
                    "project": d.get("project"),
                    "type": d.get("type"),
                    "milestone": d.get("milestone"),
                    "amount_usd": d.get("amountUsd"),
                    "paid_date": paid_date,
                    "category": d.get("category"),
                })
        except (ValueError, TypeError):
            pass

    recent.sort(key=lambda x: x["paid_date"], reverse=True)
    return recent


def find_top_recipients(financials, limit=10):
    """Find top grant recipients by total USD."""
    if not financials or not financials.get("recipients"):
        return []

    recipients = financials["recipients"]["data"]
    sorted_r = sorted(recipients, key=lambda x: x.get("usd", 0) or 0, reverse=True)

    return [
        {
            "recipient": r["recipient"],
            "total_usd": r.get("usd", 0),
            "total_zec": r.get("zec", 0),
            "usd_paid": r.get("usdPaid", 0),
            "grants": r.get("grants", 0),
            "payments": r.get("payments", 0),
            "last_paid": r.get("lastPaid"),
        }
        for r in sorted_r[:limit]
    ]


def analyze_meeting_activity(minutes_data):
    """Analyze recent meeting minutes for patterns."""
    if not minutes_data:
        return None

    minutes = minutes_data.get("minutes", [])
    if not minutes:
        return None

    total_views = sum(m.get("views", 0) for m in minutes)
    total_replies = sum(m.get("reply_count", 0) for m in minutes)
    total_decisions = sum(len(m.get("grants_discussed", [])) for m in minutes)

    return {
        "meetings_analyzed": len(minutes),
        "total_views": total_views,
        "avg_views": round(total_views / len(minutes), 1),
        "total_replies": total_replies,
        "total_decisions_extracted": total_decisions,
        "most_recent": minutes[0].get("title") if minutes else None,
        "most_recent_date": minutes[0].get("meeting_date") if minutes else None,
    }


def build_health_report(data):
    """Build the complete grant health report."""
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": "weekly",
    }

    # Delivery metrics
    delivery = analyze_delivery_rate(data.get("financials"))
    if delivery:
        report["delivery_metrics"] = delivery

    # Stalled grants
    stalled = find_stalled_grants(data.get("financials"), days_threshold=60)
    report["stalled_grants"] = {
        "count": len(stalled),
        "threshold_days": 60,
        "grants": stalled,
    }

    # Recent activity (last 30 days)
    recent = find_recently_completed(data.get("financials"), days=30)
    report["recent_payments"] = {
        "count": len(recent),
        "period_days": 30,
        "payments": recent[:20],  # Top 20 most recent
    }

    # Top recipients
    top = find_top_recipients(data.get("financials"))
    report["top_recipients"] = top

    # Meeting activity
    meeting_analysis = analyze_meeting_activity(data.get("minutes"))
    if meeting_analysis:
        report["meeting_activity"] = meeting_analysis

    # GitHub issue stats
    if data.get("github"):
        gh = data["github"]
        statuses = {}
        for g in gh.get("grants", []):
            s = g.get("status", "unknown")
            statuses[s] = statuses.get(s, 0) + 1
        report["github_issue_stats"] = {
            "total_issues": gh.get("total_issues", 0),
            "status_breakdown": statuses,
        }

    return report


def save_report(report, output_path="data/grant_health.json"):
    """Save health report to JSON."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Saved health report to {output_path}")


if __name__ == "__main__":
    print("Loading scraped data...")
    data = load_data()

    print("Building health report...")
    report = build_health_report(data)
    save_report(report)

    # Print summary
    dm = report.get("delivery_metrics", {})
    print(f"\n=== GRANT HEALTH SUMMARY ===")
    print(f"Total grants tracked: {dm.get('total_grants', '?')}")
    print(f"Milestone delivery rate: {dm.get('milestone_delivery_rate', '?')}%")
    print(f"Total USD committed: ${dm.get('total_usd_committed', 0):,.0f}")
    print(f"Total ZEC disbursed: {dm.get('total_zec_disbursed', 0):,.2f}")

    stalled = report.get("stalled_grants", {})
    print(f"\nStalled grants (>60 days no payment): {stalled.get('count', 0)}")
    for g in stalled.get("grants", [])[:5]:
        print(f"  {g['grant'][:50]} — ${g['usd']:,.0f} — {g['completion_pct']}% complete — {g.get('days_since_payment', '?')} days")

    recent = report.get("recent_payments", {})
    print(f"\nRecent payments (last 30 days): {recent.get('count', 0)}")
    for p in recent.get("payments", [])[:5]:
        print(f"  {p['project'][:40]} — ${p.get('amount_usd', 0):,.0f} — {p['paid_date']}")
