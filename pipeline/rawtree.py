"""Thin RawTree REST helpers. Docs: https://rawtree.com/docs/reference/api"""

import httpx

import config


def _headers():
    return {
        "Authorization": f"Bearer {config.RAWTREE_API_KEY}",
        "Content-Type": "application/json",
    }


def _params():
    return {"database": config.RAWTREE_DATABASE}


def insert(table, rows):
    """POST rows (list of dicts) to a table. The table is created on first insert."""
    r = httpx.post(
        f"{config.RAWTREE_API_URL}/v1/tables/{table}",
        headers=_headers(),
        params=_params(),
        json=rows,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def query(sql):
    """Run read-only SQL and return the rows as a list of dicts."""
    r = httpx.post(
        f"{config.RAWTREE_API_URL}/v1/query",
        headers=_headers(),
        params=_params(),
        json={"sql": sql, "format": "JSON"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("data", [])


def quote(value):
    """Quote a string as a SQL literal, since the query endpoint takes raw SQL."""
    return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"


def run_sql(name, category=""):
    """Run sql/{name}.sql with its {placeholders} filled in and quoted."""
    sql = (config.SQL_DIR / f"{name}.sql").read_text()
    values = {
        "table": config.RAWTREE_TABLE,  # identifier from config, not user input
        "neighborhood": quote(config.NEIGHBORHOOD),
        "days": str(int(config.DAYS_AHEAD)),
        "category": quote(category),
    }
    for key, value in values.items():
        sql = sql.replace("{" + key + "}", value)
    return query(sql)
