"""
Scrape ZCG meeting minutes from Zcash Community Forum JSON API.
Extracts: dates, grants discussed, votes, decisions, amounts.
"""

import urllib.request
import json
import os
import re
import time
from datetime import datetime, timezone

FORUM_BASE = "https://forum.zcashcommunity.com"
# Category: Community Grants > Community Grants Updates
CATEGORY_ID = 34
CATEGORY_SLUG = "grants/zomg-updates"


def fetch_forum_json(url):
    """Fetch JSON from Discourse forum API."""
    print(f"  Fetching {url}...")
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "zcash-grant-tracker",
    })
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def fetch_category_topics(category_id=CATEGORY_ID, slug=CATEGORY_SLUG):
    """Fetch all topics in the ZCG updates category."""
    topics = []
    page = 0
    while True:
        url = f"{FORUM_BASE}/c/{slug}/{category_id}.json?page={page}"
        data = fetch_forum_json(url)

        topic_list = data.get("topic_list", {}).get("topics", [])
        if not topic_list:
            break
        topics.extend(topic_list)

        more_url = data.get("topic_list", {}).get("more_topics_url")
        if not more_url:
            break
        page += 1
        time.sleep(1)

    return topics


def is_meeting_minutes(topic):
    """Check if a topic is meeting minutes (not an announcement or other post)."""
    title = topic.get("title", "").lower()
    return "meeting minutes" in title or "meeting-minutes" in title


def fetch_topic_content(topic_id):
    """Fetch the full first post content of a topic."""
    url = f"{FORUM_BASE}/t/{topic_id}.json"
    data = fetch_forum_json(url)
    posts = data.get("post_stream", {}).get("posts", [])
    if posts:
        return {
            "topic_id": topic_id,
            "title": data.get("title", ""),
            "created_at": data.get("created_at", ""),
            "url": f"{FORUM_BASE}/t/{data.get('slug', '')}/{topic_id}",
            "content": posts[0].get("cooked", ""),  # HTML content
            "raw": posts[0].get("raw", ""),  # Markdown content (if available)
            "views": data.get("views", 0),
            "reply_count": data.get("reply_count", 0),
            "like_count": data.get("like_count", 0),
        }
    return None


def extract_date_from_title(title):
    """Extract meeting date from title like 'Meeting Minutes 10/23/2026'."""
    patterns = [
        r'(\d{1,2}/\d{1,2}/\d{4})',
        r'(\d{1,2}-\d{1,2}-\d{4})',
        r'(\w+ \d{1,2},?\s*\d{4})',
        r'(\d{4}-\d{2}-\d{2})',
    ]
    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            return match.group(1)
    return None


def parse_grants_discussed(content):
    """Extract grants discussed from meeting minutes HTML content."""
    grants = []

    # Look for grant names with amounts — common patterns in ZCG minutes
    # Pattern: "Grant Name — $XX,XXX" or "Grant Name ($XX,XXX)"
    amount_patterns = [
        r'(?:Grant[:\s]+)?(.+?)\s*[-–—]\s*\$?([\d,]+(?:\.\d{2})?)',
        r'(?:Grant[:\s]+)?(.+?)\s*\(\$?([\d,]+(?:\.\d{2})?)\)',
    ]

    # Look for vote patterns: "Approved 3-2" or "Declined 1-4"
    vote_pattern = re.compile(
        r'(approved|declined|deferred|tabled)\s*'
        r'(?:[\(-]?\s*(\d)\s*[-–/]\s*(\d)\s*[\)-]?)?',
        re.IGNORECASE
    )

    for match in vote_pattern.finditer(content):
        decision = match.group(1).lower()
        yes_votes = match.group(2)
        no_votes = match.group(3)
        grants.append({
            "decision": decision,
            "yes_votes": int(yes_votes) if yes_votes else None,
            "no_votes": int(no_votes) if no_votes else None,
            "context": content[max(0, match.start()-100):match.end()+50].strip(),
        })

    return grants


def scrape_meeting_minutes(limit=None):
    """Main scraper: fetch all ZCG meeting minutes."""
    print("Fetching ZCG meeting minutes topics...")
    topics = fetch_category_topics()
    print(f"  Found {len(topics)} topics in category.")

    minutes_topics = [t for t in topics if is_meeting_minutes(t)]
    print(f"  {len(minutes_topics)} are meeting minutes.")

    if limit:
        minutes_topics = minutes_topics[:limit]
        print(f"  Limited to {limit} most recent.")

    minutes = []
    for i, topic in enumerate(minutes_topics):
        topic_id = topic["id"]
        title = topic.get("title", "")
        print(f"  [{i+1}/{len(minutes_topics)}] {title[:60]}...")

        content = fetch_topic_content(topic_id)
        if content:
            content["meeting_date"] = extract_date_from_title(title)
            content["grants_discussed"] = parse_grants_discussed(
                content.get("content", "")
            )
            minutes.append(content)
        time.sleep(1)

    return minutes


def save_minutes(minutes, output_path="data/meeting_minutes.json"):
    """Save meeting minutes to JSON."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Don't save full HTML content to keep file manageable
    slim = []
    for m in minutes:
        slim.append({
            "topic_id": m["topic_id"],
            "title": m["title"],
            "meeting_date": m.get("meeting_date"),
            "created_at": m["created_at"],
            "url": m["url"],
            "views": m["views"],
            "reply_count": m["reply_count"],
            "like_count": m["like_count"],
            "grants_discussed": m.get("grants_discussed", []),
            "content_length": len(m.get("content", "")),
        })

    with open(output_path, "w") as f:
        json.dump({
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "total_minutes": len(slim),
            "minutes": slim,
        }, f, indent=2)
    print(f"Saved {len(slim)} meeting minutes to {output_path}")

    # Also save full content for analysis
    full_path = output_path.replace(".json", "_full.json")
    with open(full_path, "w") as f:
        json.dump(minutes, f, indent=2)
    print(f"Saved full content to {full_path}")


if __name__ == "__main__":
    # Fetch last 10 meeting minutes for MVP
    minutes = scrape_meeting_minutes(limit=10)
    save_minutes(minutes)

    print(f"\nScraped {len(minutes)} meeting minutes.")
    for m in minutes:
        print(f"  {m.get('meeting_date', '?')}: {m['title'][:60]} ({m['views']} views)")
