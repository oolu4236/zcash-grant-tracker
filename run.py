"""
Main pipeline runner.
Executes: scrape → analyze → generate report.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers.github_grants import scrape_grants, save_grants
from scrapers.openzcash import scrape_financials, save_financials
from scrapers.forum_minutes import scrape_meeting_minutes, save_minutes
from analysis.grant_health import load_data, build_health_report, save_report as save_health
from reports.generate import load_health_data, generate_markdown_report, save_report


def main():
    print("=" * 60)
    print("ZCASH GRANT ACCOUNTABILITY TRACKER")
    print("=" * 60)

    # Step 1: Scrape
    print("\n[1/4] Scraping GitHub grant issues...")
    grants = scrape_grants(fetch_events_for_approved=True)
    save_grants(grants)

    print("\n[2/4] Scraping OpenZcash financial data...")
    financials = scrape_financials()
    save_financials(financials)

    print("\n[3/4] Scraping ZCG meeting minutes (last 10)...")
    minutes = scrape_meeting_minutes(limit=10)
    save_minutes(minutes)

    # Step 2: Analyze
    print("\n[4/4] Analyzing grant health...")
    data = load_data()
    health = build_health_report(data)
    save_health(health)

    # Step 3: Generate report
    print("\nGenerating Weekly Grant Health Report...")
    health_data = load_health_data()
    markdown = generate_markdown_report(health_data)
    report_path = save_report(markdown)

    print(f"\n{'=' * 60}")
    print("PIPELINE COMPLETE")
    print(f"{'=' * 60}")
    print(f"Report: {report_path}")
    print(f"Health data: data/grant_health.json")

    # Print headline stats
    dm = health.get("delivery_metrics", {})
    stalled = health.get("stalled_grants", {})
    print(f"\nHeadline: {dm.get('total_grants', '?')} grants tracked, "
          f"{dm.get('milestone_delivery_rate', '?')}% delivery rate, "
          f"{stalled.get('count', '?')} stalled")


if __name__ == "__main__":
    main()
