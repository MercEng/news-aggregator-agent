import json
from collections import Counter
from datetime import UTC, datetime

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import config
from pipeline import ingest, normalize, rawtree, render

app = FastAPI(title="Local Pulse")
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")

# Status of the background jobs, polled by the page via GET /status.
jobs = {
    "refresh": {"state": "idle", "detail": "", "at": ""},
    "render": {"state": "idle", "detail": "", "at": ""},
}


def _set(job, state, detail=""):
    jobs[job] = {"state": state, "detail": detail, "at": datetime.now(UTC).isoformat()}


def _cached_events():
    if not config.EVENTS_FILE.exists():
        return []
    return json.loads(config.EVENTS_FILE.read_text())


def _run_refresh(use_cache):
    try:
        _set("refresh", "running", "scraping with Nimble" + (" (cached)" if use_cache else ""))
        events = normalize.run(use_cache)
        _set("refresh", "running", f"loading {len(events)} events into RawTree")
        inserted = ingest.ingest(events)
        _set("refresh", "done", f"{len(events)} events, {inserted} rows inserted")
    except Exception as e:
        _set("refresh", "error", str(e))


def _run_render(draft):
    try:
        _set("render", "running", "writing script")
        render.build_script()
        _set("render", "running", "rendering scenes with FLUX 3" + (" (draft)" if draft else ""))
        render.render_all(draft=draft, use_cache=False)
        _set("render", "done", "final.mp4 ready")
    except Exception as e:
        _set("render", "error", str(e))


@app.get("/")
def index():
    return FileResponse(config.STATIC_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "neighborhood": config.NEIGHBORHOOD}


@app.get("/status")
def status():
    return {"neighborhood": config.NEIGHBORHOOD, "jobs": jobs}


@app.post("/refresh")
def refresh(background: BackgroundTasks, use_cache: bool = True):
    if jobs["refresh"]["state"] == "running":
        raise HTTPException(409, "refresh already running")
    _set("refresh", "running", "starting")
    background.add_task(_run_refresh, use_cache)
    return jobs["refresh"]


@app.get("/events")
def events(category: str = ""):
    try:
        return {"source": "rawtree", "events": rawtree.run_sql("this_week", category=category)}
    except Exception:
        cached = [e for e in _cached_events() if not category or e["category"] == category]
        return {"source": "cache", "events": cached}


@app.get("/trending")
def trending():
    try:
        rows = rawtree.run_sql("trending")
        source = "rawtree"
    except Exception:
        cached = _cached_events()
        rows = [
            {"kind": kind, "name": name, "events": n}
            for kind in ("category", "store")
            for name, n in Counter(e[kind] for e in cached).most_common()
        ]
        source = "cache"
    return {
        "source": source,
        "categories": [r for r in rows if r["kind"] == "category"],
        "stores": [r for r in rows if r["kind"] == "store"],
    }


@app.post("/render")
def render_video(background: BackgroundTasks, hd: bool = False):
    if jobs["render"]["state"] == "running":
        raise HTTPException(409, "render already running")
    _set("render", "running", "starting")
    background.add_task(_run_render, not hd)
    return jobs["render"]


@app.get("/video")
def video():
    path = config.VIDEOS_DIR / "final.mp4"
    script = json.loads(config.SCRIPT_FILE.read_text()) if config.SCRIPT_FILE.exists() else None
    url = f"/static/videos/final.mp4?v={int(path.stat().st_mtime)}" if path.exists() else None
    return {"url": url, "script": script}
