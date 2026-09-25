"""Push normalized events from data/events.json to RawTree.

Inserts are append only; queries dedupe with LIMIT 1 BY event_id.
"""

import json

import config
from pipeline import rawtree

BATCH_SIZE = 100


def ingest(events=None):
    if events is None:
        events = json.loads(config.EVENTS_FILE.read_text())
    inserted = 0
    for i in range(0, len(events), BATCH_SIZE):
        res = rawtree.insert(config.RAWTREE_TABLE, events[i : i + BATCH_SIZE])
        inserted += int(res.get("inserted", 0))
    return inserted


if __name__ == "__main__":
    print(f"inserted {ingest()} rows into {config.RAWTREE_TABLE}")
