"""
Generate the Weekly Grant Health Report from analyzed data.
Outputs: Markdown for forum posting, structured JSON for archiving.
"""

import json
import os
from datetime import datetime, timezone


def load_health_data(path="data/grant_health.json"):
    """Load the analyzed health report."""
    with open(path) as f:
        return json.load(f)


def format_currency(amount):
    """Format USD amount."""
    if amount is None:
        return "N/A"
    if amount >= 1_000_000:
        return f"${amount/1_000_000:.1f}M"
    if amount >= 1_000:
        return f"${amount:,.0f}"
    return f"${amount:.0f}"


def generate_markdown_report(health):
    """Generate forum-ready markdown report."""
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%B %d, %Y")

    dm = health.get("delivery_metrics", {})
    stalled = health.get("stalled_grants", {})
    recent = health.get("recent_payments", {})
    top = health.get("top_recipients", [])
    meetings = health.get("meeting_activity", {})

    lines = []
    lines.append(f"## 📊 Zcash Grant Health Report — Week of {date_str}")
    lines.append("")
    lines.append("*Automated accountability tracking for ZCG and CDRGP grants. "
                  "All data sourced from [OpenZcash](https://openzcash.org/zcg), "
                  "[GitHub](https://github.com/ZcashCommunityGrants/zcashcommunitygrants), "
                  "and [ZCG meeting minutes](https://forum.zcashcommunity.com/c/grants/zomg-updates/34).*")
    lines.append("")

    # Headline numbers
    lines.append("---")
    lines.append("")
    lines.append("### At a Glance")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Total grants tracked | {dm.get('total_grants', '?')} |")
    lines.append(f"| Total USD committed | {format_currency(dm.get('total_usd_committed', 0))} |")
    lines.append(f"| Total ZEC disbursed | {dm.get('total_zec_disbursed', 0):,.0f} ZEC |")
    lines.append(f"| Milestone delivery rate | {dm.get('milestone_delivery_rate', '?')}% |")
    lines.append(f"| Milestones paid / total | {dm.get('paid_milestones', '?')} / {dm.get('total_milestones', '?')} |")
    lines.append(f"| Stalled grants (>60 days) | {stalled.get('count', '?')} |")
    lines.append(f"| Payments last 30 days | {recent.get('count', '?')} |")
    lines.append("")

    # Status breakdown
    status_map = dm.get("status_breakdown", {})
    if status_map:
        lines.append("### Grant Status Breakdown")
        lines.append("")
        lines.append("| Status | Count |")
        lines.append("|---|---|")
        for status, count in sorted(status_map.items(), key=lambda x: -x[1]):
            lines.append(f"| {status} | {count} |")
        lines.append("")

    # Category breakdown
    cats = dm.get("category_breakdown", {})
    if cats:
        lines.append("### Funding by Category")
        lines.append("")
        lines.append("| Category | Grants | USD Committed |")
        lines.append("|---|---|---|")
        for cat, info in sorted(cats.items(), key=lambda x: -x[1]["usd"]):
            lines.append(f"| {cat} | {info['count']} | {format_currency(info['usd'])} |")
        lines.append("")

    # Stalled grants
    stalled_grants = stalled.get("grants", [])
    if stalled_grants:
        lines.append("### ⚠️ Stalled Grants")
        lines.append("")
        lines.append(f"*Grants with no milestone payment in 60+ days that are not yet complete.*")
        lines.append("")
        lines.append("| Grant | Grantee | Committed | Progress | Last Payment | Days Silent |")
        lines.append("|---|---|---|---|---|---|")
        for g in stalled_grants:
            days = g.get("days_since_payment")
            days_str = f"{days}" if days else "never paid"
            note = f" ({g['note']})" if g.get("note") else ""
            lines.append(
                f"| {g['grant'][:45]} | {g['grantee']} | "
                f"{format_currency(g['usd'])} | {g['completion_pct']}% "
                f"({g['milestones_paid']}/{g['milestones']}) | "
                f"{g.get('last_paid', 'N/A')} | {days_str}{note} |"
            )
        lines.append("")

    # Recent payments
    recent_payments = recent.get("payments", [])
    if recent_payments:
        lines.append("### 💰 Recent Payments (Last 30 Days)")
        lines.append("")
        lines.append("| Project | Recipient | Type | Amount | Date |")
        lines.append("|---|---|---|---|---|")
        for p in recent_payments[:15]:
            lines.append(
                f"| {(p.get('project') or '')[:35]} | {(p.get('recipient') or '')[:20]} | "
                f"{p.get('type', '')} | {format_currency(p.get('amount_usd'))} | "
                f"{p.get('paid_date', '')} |"
            )
        if len(recent_payments) > 15:
            lines.append(f"| *...and {len(recent_payments) - 15} more* | | | | |")
        lines.append("")

    # Top recipients
    if top:
        lines.append("### 🏆 Top 10 Grant Recipients (All Time)")
        lines.append("")
        lines.append("| Recipient | Total Committed | Paid | Grants | Payments |")
        lines.append("|---|---|---|---|---|")
        for r in top:
            lines.append(
                f"| {r['recipient'][:30]} | {format_currency(r['total_usd'])} | "
                f"{format_currency(r.get('usd_paid', 0))} | {r['grants']} | {r['payments']} |"
            )
        lines.append("")

    # Meeting activity
    if meetings:
        lines.append("### 📋 Recent ZCG Meeting Activity")
        lines.append("")
        lines.append(f"- Meetings analyzed: {meetings.get('meetings_analyzed', '?')}")
        lines.append(f"- Average views per minutes post: {meetings.get('avg_views', '?')}")
        lines.append(f"- Total community replies: {meetings.get('total_replies', '?')}")
        lines.append(f"- Most recent: {meetings.get('most_recent', '?')}")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("*This report is generated by the [Zcash Grant Accountability Tracker]"
                  "(https://github.com/oolu4236/zcash-grant-tracker). "
                  "Data refreshed weekly from public APIs. "
                  "Not affiliated with ZCG or the Financial Privacy Foundation.*")
    lines.append("")
    lines.append("🛡️ Tip (shielded): "
                  "`u1ugdhhhag775002dh5yx58mw6nlvr9k2zd2lqg8nvtudgxxmntwtavkp3ushc04t0ejynf0j6rt9h4xgcumwve4dkgkq6rlcju5vcq8g2`")

    return "\n".join(lines)


def save_report(markdown, output_dir="reports"):
    """Save generated report."""
    os.makedirs(output_dir, exist_ok=True)

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    # Save markdown
    md_path = os.path.join(output_dir, f"report_{date_str}.md")
    with open(md_path, "w") as f:
        f.write(markdown)
    print(f"Saved report to {md_path}")

    # Save latest (always overwritten)
    latest_path = os.path.join(output_dir, "latest.md")
    with open(latest_path, "w") as f:
        f.write(markdown)
    print(f"Updated {latest_path}")

    return md_path


if __name__ == "__main__":
    print("Loading health data...")
    health = load_health_data()

    print("Generating report...")
    markdown = generate_markdown_report(health)
    path = save_report(markdown)

    print(f"\n{'='*60}")
    print(markdown[:2000])
    print(f"{'='*60}")
    print(f"\n[Report truncated — full version at {path}]")
