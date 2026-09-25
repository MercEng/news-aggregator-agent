# Local Pulse

An AI local news anchor for one neighborhood. Nimble web agents find what's happening at
local shops and venues this week, RawTree stores and queries it, and FLUX 3 turns the
highlights into a short narrated news video.

```
Nimble (Maps template + 6 web agents)  ->  RawTree (local_events table + SQL)  ->  FLUX 3 video
        finds stores and events                 stores, dedupes, ranks            anchor + highlights
```

## Run it

```bash
uv venv --python 3.12 && uv pip install -r requirements.txt
cp .env.example .env              # fill in NIMBLE_API_KEY, RAWTREE_API_KEY, BFL_API_KEY
.venv/bin/uvicorn main:app --reload
# open http://localhost:8000
```

Pipeline pieces can also run on their own:

```bash
python smoke_test.py [--skip-bfl]      # one call per service, prints PASS/FAIL
python -m pipeline.normalize           # scrape (cached) + clean -> data/events.json
python -m pipeline.ingest              # data/events.json -> RawTree
python -m pipeline.render --script     # write data/script.json only
python -m pipeline.render              # draft video -> static/videos/final.mp4 (--hd for final)
```

Every external response is cached (`data/raw/`, `data/events.json`, `static/videos/`), so the
demo runs without a live scrape or render.

---

## Demo script (about 60 seconds)

> **[Page open, video paused at the anchor]**
>
> "Neighborhood news is basically dead. The jazz trio on the plaza, the pop-up, the Saturday
> cleanup: it's scattered across a dozen shop websites and calendars, and nobody's covering it.
> So we built Local Pulse: an AI news anchor for one neighborhood. Today, Hayes Valley in
> San Francisco."
>
> **[Point at the event list]**
>
> "Step one is **Nimble**. We use Nimble's Google Maps template to find about 60 local shops,
> cafes and bookstores. Then we send out six Nimble web agents in parallel, one each for sales,
> pop-ups, workshops, music, food and community events. Each agent searches the live web and
> returns clean, structured JSON in our exact event schema, with a source link for every field.
> No scraping code per site, and no LLM cleanup step."
>
> **[Click a trending chip, e.g. "music"]**
>
> "Step two is **RawTree**. We push those events straight in as JSON. There's no schema to set
> up; the table appears on first insert. Everything you see here, the week's events and these
> trending counts, is a live SQL query against RawTree. Click a category and it re-queries."
>
> **[Press play]**
>
> "Step three is **FLUX 3** from Black Forest Labs. We take the top events from RawTree, turn
> them into a five-scene anchor script, and FLUX 3 renders every scene as video *with the
> narration spoken in the audio*, all in under two minutes."
>
> **[Let the video play, about 40 seconds]**
>
> "That's Local Pulse: Nimble finds it, RawTree knows it, FLUX 3 tells it."

**Optional closer:** switch to the RawTree UI, show the `local_events` table, and run
`SELECT category, count() FROM local_events GROUP BY category` live.

---

## Where each sponsor shows up

| Tool | What it does here | Where to look |
|---|---|---|
| **Nimble** | `google_maps_search` template finds local stores; 6 parallel web search agents return events as JSON matching our schema | `pipeline/scrape.py`, raw responses in `data/raw/` |
| **RawTree** | Schema-free `local_events` table; SQL for this week's events and trending counts, deduped at query time | `pipeline/rawtree.py`, `sql/this_week.sql`, `sql/trending.sql` |
| **FLUX 3 (BFL)** | Text-to-video with native audio: 5 scenes × 8 s, rendered in parallel, joined with ffmpeg | `pipeline/render.py`, output in `static/videos/` |

## Likely questions

**Where does the data come from?** Nimble's web agents search the live web: neighborhood
association calendars, venue sites, event pages. Every event keeps the URL it came from, and
the event titles on the page link to it.

**Is an LLM writing anything?** Nimble's agents do the finding and structuring. The anchor
script is a template filled from the RawTree query results, and FLUX 3 speaks it. There is no
separate LLM step in our code.

**How fresh is it?** "Refresh events" re-runs the agents (about 6 minutes live, since six agents
search in parallel). "Render video" re-renders from the latest RawTree data in about 2 minutes.
For the demo everything is cached.

**What about duplicates?** Different agents find the same event, so we dedupe on title + date
before insert, and the SQL keeps one row per `event_id` (`LIMIT 1 BY event_id`), so re-running
the pipeline never double counts.

**What does it cost?** A 40-second draft video is about 190 BFL credits. A refresh is 3 Maps
lookups plus 6 agent runs on Nimble.

**Could this work for another neighborhood?** Yes: change `NEIGHBORHOOD` in `.env` and refresh.
