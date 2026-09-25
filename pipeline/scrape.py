"""Nimble scraping. Every raw response is cached as JSON in data/raw/."""

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from nimble_python import Nimble

import config

_client = None

EVENTS_SCHEMA = {
    "type": "object",
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "store": {
                        "type": "string",
                        "description": "Business or venue hosting the event, never a street name",
                    },
                    "title": {"type": "string"},
                    "description": {"type": "string", "description": "One or two sentences"},
                    "category": {"type": "string", "enum": config.CATEGORIES},
                    "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "YYYY-MM-DD or empty"},
                    "address": {"type": "string"},
                    "url": {"type": "string", "description": "Page describing the event"},
                },
                "required": ["store", "title", "category", "start_date", "url"],
            },
        }
    },
    "required": ["events"],
}


def client():
    global _client
    if _client is None:
        _client = Nimble(api_key=config.NIMBLE_API_KEY)
    return _client


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def _cached(name, fetch, use_cache):
    """Return data/raw/{name}.json if present, else call fetch() and cache it."""
    path = config.RAW_DIR / f"{name}.json"
    if use_cache and path.exists():
        return json.loads(path.read_text())
    data = fetch()
    if hasattr(data, "model_dump"):
        data = data.model_dump(mode="json")
    path.write_text(json.dumps(data, indent=2))
    return data


def find_stores(use_cache=True):
    """Google Maps search per store query. Returns [{name, address, website}]."""
    stores = []
    for q in config.STORE_QUERIES:
        raw = _cached(
            f"maps_{_slug(q)}",
            lambda q=q: client().extract.templates.run(
                template="google_maps_search", params={"query": q}
            ),
            use_cache,
        )
        entities = (raw.get("data") or {}).get("parsing", {}).get("entities", {})
        for place in entities.get("SearchResult", []):
            stores.append(
                {
                    "name": place.get("title", ""),
                    "address": place.get("address", ""),
                    "website": (place.get("place_information") or {}).get("website_url", ""),
                }
            )
    return stores


def _run_agent(prompt, timeout=600):
    """Start a Nimble web search agent run, wait for it, return the result dict."""
    run = client().agents.run(input=prompt, output_schema=EVENTS_SCHEMA, effort=config.AGENT_EFFORT)
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = client().agents.runs.get(run.id, agent_id=run.web_search_agent_id)
        if status.completed_at or status.error:
            break
        time.sleep(5)
    else:
        raise TimeoutError(f"agent run {run.id} not done after {timeout}s")
    if status.error:
        raise RuntimeError(f"agent run {run.id} failed: {status.error}")
    return client().agents.runs.result(run.id, agent_id=run.web_search_agent_id)


def _events_from_result(raw):
    """Pull events out of an agent result, filling a missing url from its citations."""
    output = raw.get("output") or {}
    events = (output.get("content") or {}).get("events") or []
    cited = {}
    for claim in (output.get("trust") or {}).get("claims", []):
        m = re.match(r"\$\.events\[(\d+)\]", claim.get("path", ""))
        if m and claim.get("citations"):
            cited.setdefault(int(m.group(1)), claim["citations"][0].get("url"))
    for i, e in enumerate(events):
        if not e.get("url"):
            e["url"] = cited.get(i) or ""
    return events


def find_events(stores=(), use_cache=True):
    """One Nimble agent run per topic, in parallel. Returns raw event dicts."""
    start = date.today()
    end = start + timedelta(days=config.DAYS_AHEAD)
    store_names = ", ".join(s["name"] for s in stores[:25] if s["name"])

    def one(topic):
        prompt = (
            f"Find upcoming in-person {topic} in {config.NEIGHBORHOOD} "
            f"happening between {start} and {end}. Focus on local shops, cafes, bookstores, "
            f"galleries and venues. Only include events with a concrete date in that range, "
            f"and give the page URL where each event is listed."
        )
        if store_names:
            prompt += f" Local businesses worth checking include: {store_names}."
        try:
            raw = _cached(f"agent_{_slug(topic)}", lambda: _run_agent(prompt), use_cache)
        except Exception as e:  # one failed topic should not sink the scrape
            print(f"agent failed for {topic!r}: {e}")
            return []
        return _events_from_result(raw)

    with ThreadPoolExecutor(max_workers=len(config.EVENT_TOPICS)) as pool:
        batches = list(pool.map(one, config.EVENT_TOPICS))
    return [e for batch in batches for e in batch]


def run_all(use_cache=True):
    stores = find_stores(use_cache)
    events = find_events(stores, use_cache)
    return {"stores": stores, "events": events}


if __name__ == "__main__":
    out = run_all()
    print(f"stores={len(out['stores'])} events={len(out['events'])}")
