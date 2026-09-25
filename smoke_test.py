"""One call per service. Usage: python smoke_test.py [--skip-bfl]

The BFL check submits a 5 second Draft HD render (about $0.30).
"""

import sys
import time
import traceback
from datetime import UTC, datetime

import httpx

import config


def check_nimble():
    from pipeline.scrape import client

    res = client().extract.templates.run(
        template="google_maps_search", params={"query": config.STORE_QUERIES[0]}
    )
    places = res.data.parsing["entities"]["SearchResult"]
    first = places[0] if places else {}
    return f"{len(places)} places; first place keys: {sorted(first)}"


def check_rawtree():
    from pipeline import rawtree

    # Columns are inferred as Dynamic, so compare as strings.
    run_id = f"run-{datetime.now(UTC).timestamp()}"
    rawtree.insert("local_pulse_smoke_test", [{"msg": "hello", "run_id": run_id}])
    rows = rawtree.query(
        f"SELECT count() AS n FROM local_pulse_smoke_test WHERE toString(run_id) = {rawtree.quote(run_id)}"
    )
    assert rows and int(rows[0]["n"]) >= 1, f"row not found: {rows}"
    return "insert + query ok"


def check_bfl():
    headers = {"x-key": config.BFL_API_KEY}
    submit = httpx.post(
        f"{config.BFL_API_URL}/flux-3-video",
        headers=headers,
        json={
            "mode": "t2v",
            "prompt": "a sunny neighborhood street with small shops, gentle camera pan",
            "duration": 5,
            "resolution": "hd",
            "draft": True,
            "generate_audio": False,
        },
        timeout=30,
    )
    submit.raise_for_status()
    polling_url = submit.json()["polling_url"]
    deadline = time.time() + 300
    while time.time() < deadline:
        time.sleep(3)
        res = httpx.get(polling_url, headers=headers, timeout=30).json()
        if res["status"] == "Ready":
            out = config.VIDEOS_DIR / "smoke.mp4"
            out.write_bytes(httpx.get(res["result"]["sample"], timeout=120).content)
            return f"rendered {out.relative_to(config.ROOT)}"
        if res["status"] not in ("Pending", "Processing", "Queued"):
            raise RuntimeError(res["status"])
    raise TimeoutError("render not ready after 5 minutes")


def main():
    checks = {"nimble": check_nimble, "rawtree": check_rawtree}
    if "--skip-bfl" not in sys.argv:
        checks["bfl"] = check_bfl
    ok = True
    for name, fn in checks.items():
        try:
            print(f"PASS {name}: {fn()}")
        except Exception as e:
            ok = False
            print(f"FAIL {name}: {e!r}")
            if "-v" in sys.argv:
                traceback.print_exc()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
