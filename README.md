# Zcash Grant Accountability Tracker

Automated pipeline that tracks ZCG and CDRGP grant health — milestones, delivery rates, stalled grants, vote patterns — and publishes weekly Grant Health Reports.

## Data Sources

- **GitHub Issues API** — ZcashCommunityGrants/zcashcommunitygrants (grant lifecycle, labels, events)
- **OpenZcash API** — openzcash.org/api/zcg (financials, disbursements, payment schedules)
- **Forum JSON API** — forum.zcashcommunity.com (meeting minutes, votes, reasoning)
- **Grantee GitHub repos** — commit activity cross-referenced with claimed milestones

## Pipeline

```
Weekly cron → Scrape all sources → Claude API analysis → 
  → data/grant_health.json (structured)
  → Weekly Grant Health Report (forum post)
  → Notion archive
```

## Structure

```
scrapers/       — Data collection from GitHub, OpenZcash, Forum
analysis/       — Grant health scoring and Claude API analysis
reports/        — Report generation and publishing
data/           — Cached/processed data
.github/        — Actions workflows
```

## License

MIT
