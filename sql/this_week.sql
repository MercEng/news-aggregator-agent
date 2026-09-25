-- Columns are inferred as Dynamic, so cast before comparing.
SELECT
    toString(event_id) AS event_id,
    toString(store) AS store,
    toString(title) AS title,
    toString(description) AS description,
    toString(category) AS category,
    toString(start_date) AS start_date,
    toString(address) AS address,
    toString(url) AS url
FROM {table}
WHERE toString(neighborhood) = {neighborhood}
  AND toDate(toString(start_date)) BETWEEN today() AND today() + {days}
  AND ({category} = '' OR toString(category) = {category})
ORDER BY toDate(toString(start_date)), store, toString(scraped_at) DESC
LIMIT 1 BY event_id
LIMIT 100
