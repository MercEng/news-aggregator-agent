"""Every HTTP surface in the app, in one folder.

Features are grouped by feature (`api_base/item/` holds that entity's model,
schema, repository, and service). Routers are the deliberate exception: they all
look the same, and keeping them together means you can read the entire API --
paths, status codes, tags, response models -- without opening five packages.

The layer rule still holds:

    router -> service -> repository -> model

A router binds request bodies and query parameters into Pydantic schemas, calls
exactly one service method, and sets the status code. It does not touch the
database session, does not import SQLAlchemy models, and holds no business
rules. Domain errors raised by services become responses through the handlers
registered in `exceptions.py`, so routers do not catch them.

One file per feature: `routers/<feature>.py`, importing that feature's schemas
and its `<Feature>ServiceDep`.
"""
