"""Turn raw Nimble agent events into the event schema. Plain Python, no LLM."""

import hashlib
import json
import re
from datetime import UTC, date, datetime

import config


def _date(value):
    """Return value as YYYY-MM-DD, or "" if it is not a valid date."""
    try:
        return date.fromisoformat(str(value or "").strip()[:10]).isoformat()
    except ValueError:
        return ""


def _clean(text, limit=None):
    text = " ".join(str(text or "").split())
    return text[:limit] if limit else text


def normalize(raw_events, stores=()):
    today = date.today().isoformat()
    scraped_at = datetime.now(UTC).isoformat(timespec="seconds")
    addresses = {s["name"].lower(): s["address"] for s in stores if s.get("name")}
    events = {}
    seen = set()
    for e in raw_events:
        # Agents name the same host differently, e.g. "PROXY" vs "PROXY (ProxySF)".
        store = _clean(re.sub(r"\(.*?\)", "", str(e.get("store") or "")))
        title = _clean(e.get("title"))
        start, end = _date(e.get("start_date")), _date(e.get("end_date"))
        if not (store and title and start):
            continue
        if (end or start) < today:
            continue
        dedupe_key = (re.sub(r"[^a-z0-9]", "", title.lower()), start)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        category = e.get("category") if e.get("category") in config.CATEGORIES else "other"
        event_id = hashlib.sha1(f"{store}|{title}|{start}".lower().encode()).hexdigest()
        # Every field is a string so RawTree infers the same columns on every insert.
        events[event_id] = {
            "event_id": event_id,
            "store": store,
            "title": title,
            "description": _clean(e.get("description"), 300),
            "category": category,
            "start_date": start,
            "end_date": end,
            "address": _clean(e.get("address")) or addresses.get(store.lower(), ""),
            "url": _clean(e.get("url")),
            "neighborhood": config.NEIGHBORHOOD,
            "source": "agent",
            "scraped_at": scraped_at,
        }
    return sorted(events.values(), key=lambda ev: (ev["start_date"], ev["store"]))


def run(use_cache=True):
    from pipeline import scrape

    raw = scrape.run_all(use_cache)
    events = normalize(raw["events"], raw["stores"])
    config.EVENTS_FILE.write_text(json.dumps(events, indent=2))
    return events


if __name__ == "__main__":
    events = run()
    print(f"{len(events)} events -> {config.EVENTS_FILE.relative_to(config.ROOT)}")
    for e in events:
        print(f"{e['start_date']}  {e['category']:<9}  {e['store']}: {e['title']}")
