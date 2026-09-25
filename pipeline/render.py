"""Build a news anchor script from RawTree data and render it with FLUX 3 Video.

Docs: https://docs.bfl.ai/flux_3/flux3_video
"""

import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import httpx

import config
from pipeline import rawtree

SCENE_SECONDS = 8
MAX_HIGHLIGHTS = 3

ANCHOR_SET = (
    "A friendly local news anchor at a bright, modern news desk, a large window behind "
    "showing a leafy San Francisco street with Victorian houses and small shopfronts, "
    "warm morning light, broadcast camera framing, no logos, no on-screen text"
)

CATEGORY_VISUALS = {
    "sale": "a charming neighborhood boutique with sale racks and shoppers browsing",
    "launch": "a stylish shop interior with a new product display and a small crowd",
    "workshop": "a cozy shop space with a small group at a table learning a craft",
    "popup": "a colorful pop-up stand on a sidewalk plaza with people browsing",
    "music": "an evening outdoor plaza with string lights and a small band performing",
    "food": "a lively outdoor farmers' market with fruit and vegetable stalls",
    "community": "neighbors gathering on a sunny tree-lined street for a community event",
    "other": "a lively tree-lined shopping street with cafes and small shops at golden hour",
}


def _when(start_date):
    d = date.fromisoformat(start_date)
    days = (d - date.today()).days
    if days <= 0:
        return "today"
    if days == 1:
        return "tomorrow"
    return f"this {d.strftime('%A')}" if days < 7 else f"on {d.strftime('%A, %B %-d')}"


def _upper_first(text):
    return text[:1].upper() + text[1:]


def _load_events():
    try:
        return rawtree.run_sql("this_week"), rawtree.run_sql("trending")
    except Exception as e:  # RawTree down: fall back to the local copy
        print(f"RawTree query failed, using {config.EVENTS_FILE.name}: {e}")
        return json.loads(config.EVENTS_FILE.read_text()), []


def _pick_highlights(events):
    """Soonest events, spread across days, stores and categories where possible."""
    picked = []
    rules = [("start_date", "store", "category"), ("store", "category"), ("store",), ()]
    for keys in rules:
        for e in events:
            if len(picked) == MAX_HIGHLIGHTS:
                return picked
            if e in picked or any(e[k] == p[k] for p in picked for k in keys):
                continue
            picked.append(e)
    return picked


def _short_title(title):
    """'Live Music: LAMb Trio + raffle' -> 'LAMb Trio' so the narration stays short."""
    title = title.split(" + ")[0]
    tail = title.rsplit(":", 1)[-1].strip()
    return tail if len(tail.split()) >= 2 else title


def build_script():
    events, trending = _load_events()
    if not events:
        raise RuntimeError("no events this week; run the refresh first")
    place = config.NEIGHBORHOOD.split(",")[0]
    top = [t["name"] for t in trending if t["kind"] == "category"][:2]
    vibe = f", with lots of {' and '.join(top)} on the calendar" if top else ""

    scenes = [
        {
            "kind": "intro",
            "visual": ANCHOR_SET,
            "narration": f"Good morning, {place}! Here's what's happening this week{vibe}.",
        }
    ]
    for e in _pick_highlights(events):
        scenes.append(
            {
                "kind": "highlight",
                "event_id": e.get("event_id", ""),
                "visual": CATEGORY_VISUALS.get(e["category"], CATEGORY_VISUALS["other"])
                + ", handheld documentary style, no logos, no readable text",
                "narration": f"{_upper_first(_when(e['start_date']))}, {_short_title(e['title'])} "
                f"at {e['store']}.",
            }
        )
    scenes.append(
        {
            "kind": "outro",
            "visual": ANCHOR_SET,
            "narration": f"That's your Local Pulse for {place}. Get out there and enjoy it!",
        }
    )
    script = {"neighborhood": config.NEIGHBORHOOD, "date": date.today().isoformat(), "scenes": scenes}
    config.SCRIPT_FILE.write_text(json.dumps(script, indent=2))
    return script


def _prompt(scene):
    if scene["kind"] == "highlight":
        return f'{scene["visual"]}. A warm narrator voice-over says: "{scene["narration"]}"'
    return f'{scene["visual"]}. The anchor looks into the camera and says: "{scene["narration"]}"'


def render_scene(scene, index, draft=True, use_cache=True, timeout=600):
    """Render one scene to static/videos/scene_{index}.mp4 and return the path."""
    out = config.VIDEOS_DIR / f"scene_{index}{'_draft' if draft else ''}.mp4"
    if use_cache and out.exists():
        return out
    headers = {"x-key": config.BFL_API_KEY}
    body = {
        "mode": "t2v",
        "prompt": _prompt(scene),
        "duration": SCENE_SECONDS,
        "resolution": "hd",
        "aspect_ratio": "16:9",
        "generate_audio": True,
    }
    if draft:
        body["draft"] = True
    submit = httpx.post(f"{config.BFL_API_URL}/flux-3-video", headers=headers, json=body, timeout=60)
    submit.raise_for_status()
    polling_url = submit.json()["polling_url"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(3)
        res = httpx.get(polling_url, headers=headers, timeout=30).json()
        status = res.get("status")
        if status == "Ready":
            # The signed URL expires after about 10 minutes, so download right away.
            out.write_bytes(httpx.get(res["result"]["sample"], timeout=300).content)
            return out
        if status in ("Error", "Failed", "Request Moderated", "Content Moderated"):
            raise RuntimeError(f"scene {index} {status}: {res}")
    raise TimeoutError(f"scene {index} not ready after {timeout}s")


def concat(paths, out):
    """Join clips with ffmpeg, re-encoding so mismatched streams still line up."""
    inputs = [arg for p in paths for arg in ("-i", str(p))]
    streams = "".join(f"[{i}:v][{i}:a]" for i in range(len(paths)))
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *inputs,
         "-filter_complex", f"{streams}concat=n={len(paths)}:v=1:a=1[v][a]",
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-movflags", "+faststart", str(out)],
        check=True,
    )
    return out


def render_all(draft=True, use_cache=True):
    if use_cache and config.SCRIPT_FILE.exists():
        script = json.loads(config.SCRIPT_FILE.read_text())
    else:
        script = build_script()
    scenes = script["scenes"]
    with ThreadPoolExecutor(max_workers=len(scenes)) as pool:
        paths = list(pool.map(lambda i: render_scene(scenes[i], i, draft, use_cache), range(len(scenes))))
    return concat(paths, config.VIDEOS_DIR / "final.mp4")


if __name__ == "__main__":
    import sys

    if "--script" in sys.argv:
        print(json.dumps(build_script(), indent=2))
    else:
        print(render_all(draft="--hd" not in sys.argv, use_cache="--fresh" not in sys.argv))
