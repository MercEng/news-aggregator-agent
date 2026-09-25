-- Distinct events per category and per store over the next week.
SELECT kind, name, events FROM (
    SELECT 'category' AS kind, toString(category) AS name, uniqExact(toString(event_id)) AS events
    FROM {table}
    WHERE toString(neighborhood) = {neighborhood}
      AND toDate(toString(start_date)) BETWEEN today() AND today() + {days}
    GROUP BY name
    UNION ALL
    SELECT 'store' AS kind, toString(store) AS name, uniqExact(toString(event_id)) AS events
    FROM {table}
    WHERE toString(neighborhood) = {neighborhood}
      AND toDate(toString(start_date)) BETWEEN today() AND today() + {days}
    GROUP BY name
)
ORDER BY kind, events DESC, name
