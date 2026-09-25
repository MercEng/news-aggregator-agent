"""The `item` feature -- the worked example. Delete this package for a blank service.

Everything about one entity lives in one folder:

    model.py         SQLAlchemy table
    schema.py        Pydantic request/response types
    repository.py    all SQL for this entity
    service.py       all business rules for this entity
    dependencies.py  FastAPI wiring: session -> repository -> service

The router is the one piece that lives elsewhere, in `api_base/routers/item.py`,
so that every HTTP surface in the app can be read side by side.

Grouping by feature does not relax the layering rule -- it just puts the layers
next to each other:

    router -> service -> repository -> model

Each layer talks only to the one below it.

- Routers bind schemas and set status codes. They never touch the session or a
  SQLAlchemy model, and they never contain business rules.
- Services hold the rules. They never write SQL and never raise `HTTPException`
  -- they raise the domain errors in `api_base/exceptions.py`, which is why
  they can be unit tested with a stub repository and no database.
- Repositories own every SQL statement and return models or `None`. "No row" is
  a fact; "404" is a decision, and that decision belongs to the service.
- Models are the table. They never leave this package -- services convert them
  to schemas, and a SQLAlchemy model must never appear in a router signature.
"""
