# api-base

A GitHub **template repository** for FastAPI services. It is not a library and
not a framework — there is nothing to install and nothing to import. You copy
it, rename it, and edit it.

It is deliberately small. The whole thing is readable in twenty minutes, and
every part you do not want can be deleted without unpicking anything else.

What you get:

- Python 3.12, [uv](https://docs.astral.sh/uv/), FastAPI, SQLAlchemy 2.0 async
  with `asyncpg`, Pydantic v2
- Code grouped by feature, with a strict layering rule inside each one (below),
  and a worked example feature
- A consistent error envelope, structured JSON logging, liveness and readiness
  probes
- `pytest` covering all three layers, `ruff`, `pre-commit`, a non-root
  multi-stage `Dockerfile`, `docker compose`, and GitHub Actions CI

---

## Using this template

Click the green **Use this template** button on GitHub, or:

```bash
gh repo create my-new-api --template <org>/api-base --private --clone
cd my-new-api
```

This produces a fresh repository with a single initial commit — no fork
relationship, no upstream link.

### Step 1: run bootstrap

Do this before anything else. It needs nothing installed but Python.

```bash
python bootstrap.py my-new-api
```

It renames `src/api_base/` to `src/my_new_api/`, rewrites every reference to
`api-base` and `api_base` across the repo, replaces this README with a project
README, deletes itself, and runs `git add -A`. Commit the result.

The name must be lowercase with dashes. The package name is derived from it by
replacing dashes with underscores.

### Step 2: local setup

```bash
cp .env.example .env          # edit DATABASE_URL if you are not using compose
uv sync                       # creates .venv and installs everything
docker compose up -d db       # Postgres on localhost:5432
uv run uvicorn api_base.main:app --reload
```

OpenAPI docs: <http://localhost:8000/docs>.

This service does not own its schema — see [Migrations](#migrations).

Or run the API and Postgres together in containers — this builds the image,
waits for the database healthcheck, and serves:

```bash
docker compose up --build
```

### Step 3: checks

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
uv run pre-commit install     # once, so the above run on every commit
```

Tests that need a database use `TEST_DATABASE_URL` and skip with a message if
it is unreachable, so `uv run pytest` works on a fresh clone. CI always has
Postgres, so nothing skips there. The service tests never need a database at
all.

### Step 4: strip what you do not need

The example `item` feature exists to show the pattern, not because you need it.
Because a feature is one folder, removing it is mostly one `rm -rf`:

```bash
rm -rf src/api_base/item                                  # model, schema, repository, service, wiring
rm src/api_base/routers/item.py                           # its HTTP surface
rm tests/test_item_api.py tests/test_item_service.py
```

One file outside the feature knows it exists, and marks the spot with
`# --- example feature ---` / `# --- end example feature ---`:
`src/api_base/main.py` (the import and the `include_router` call). Delete that
block:

```bash
python - <<'EOF'
import re
from pathlib import Path

path = Path("src/api_base/main.py")
path.write_text(
    re.sub(
        r"[ \t]*# --- example feature ---.*?# --- end example feature ---\n",
        "",
        path.read_text(),
        flags=re.DOTALL,
    )
)
EOF

# deleting the import block leaves stray blank lines; --fix tidies them
uv run ruff check --fix . && uv run ruff format . && uv run pytest
```

What is left is a working app with the health endpoints and nothing else.

### Step 5: the one manual step on GitHub

After pushing, go to **Settings → General** and check **Template repository**.
That is what makes the "Use this template" button appear for consumers.

---

## How the code is organised

**By feature, not by layer.** Everything about one entity lives in one folder,
so adding a feature is one new directory and deleting one is `rm -rf`:

```
src/api_base/
  main.py             create_app(): routers, CORS, error handlers, lifespan, logging
  config.py           Settings via pydantic-settings, cached with lru_cache
  db.py               declarative Base + engine, session factory, get_session, ping
  repository.py       the generic BaseRepository every feature subclasses
  exceptions.py       domain errors + the handlers that map them to responses
  dependencies.py     SessionDep, the one dependency every feature shares

  item/               <-- one folder per feature
    model.py          SQLAlchemy table
    schema.py         Pydantic request/response types
    repository.py     all SQL for this entity
    service.py        all business rules for this entity
    dependencies.py   wiring: session -> repository -> service

  routers/            <-- every HTTP surface, together
    health.py
    item.py
```

Routers are the deliberate exception to feature grouping. They all look the
same, and keeping them in one folder means you can read the entire API — paths,
status codes, tags, response models — without opening every feature package.

The top-level modules are the shared kernel: the things a second feature would
otherwise duplicate. If you find yourself adding to them for one feature's sake,
it belongs in that feature's folder instead.

## The layering rule

Grouping by feature does not relax the layering rule — it just puts the layers
next to each other:

```
router  ->  service  ->  repository  ->  model
```

**Each layer talks only to the one below it.** This is the single rule this repo
exists to establish. It is restated in `item/__init__.py`, in
`routers/__init__.py`, and in a one-line `Layer:` header on each module.

| Layer | Owns | Never does |
| --- | --- | --- |
| **router** | HTTP: binding request bodies and query parameters to schemas, status codes, OpenAPI metadata | Touch the session or a SQLAlchemy model; contain business rules |
| **service** | Business rules, orchestration, model → schema conversion | Write SQL; raise `HTTPException` |
| **repository** | Every SQL statement in the application | Raise HTTP errors, or decide what "not found" means |
| **model** | The table definition | Leave the repository layer |

Three consequences worth stating out loud:

- **Repositories return `None`, services raise.** "No row" is a fact; "404" is
  a decision. Keeping them apart is why a service is unit-testable with a stub
  repository and no database.
- **Schemas are the boundary.** Pydantic schemas cross the router/service
  boundary in both directions. SQLAlchemy models never appear in a router
  signature. If you find yourself importing a `model` in a router, the design
  has slipped.
- **A model is not a schema.** The model is the table: columns, indexes,
  constraints. The schema is the contract: what a client may send and may see.
  They diverge constantly — `ItemCreate` has no `id`, `ItemPage` has no table
  behind it, and a `User` model would hold a `password_hash` that must never
  appear in any schema. One class for both means a column rename is silently an
  API break.

Routers do not catch domain errors. `NotFoundError` and `ConflictError` become
404 and 409 through handlers registered once in `exceptions.py`, so every error
in the app comes back in the same envelope:

```json
{ "error": { "code": "conflict", "message": "...", "details": {} } }
```

### Why `src/`?

`src/` is the standard Python "src layout", not a versioning scheme — it holds
exactly one importable package, always. Its purpose is that tests import the
*installed* package rather than accidentally picking up the working directory,
which catches files missing from the built wheel. API versioning is the
`API_PREFIX` setting (`/api/v1`), not a directory.

---

## Adding a new feature

One folder, four files inside it, one router, two lines of registration. Build
bottom up, so every step compiles against the one before it. Replace `Widget`
and `widgets` throughout — this is the checklist to copy.

```bash
mkdir src/api_base/widget
touch src/api_base/widget/{__init__,model,schema,repository,service,dependencies}.py
touch src/api_base/routers/widget.py
```

### 1. Model — `src/api_base/widget/model.py`

```python
"""Layer: model. The table, and nothing else. Never leaves this package."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from api_base.db import TimestampedBase


class Widget(TimestampedBase):
    __tablename__ = "widgets"

    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
```

`TimestampedBase` gives you `id` (UUID), `created_at`, and `updated_at`.

### 2. Schema — `src/api_base/widget/schema.py`

```python
"""Layer: schema. The public contract."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WidgetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    is_active: bool = True


class WidgetUpdate(BaseModel):  # every field optional: this is a PATCH
    name: str | None = Field(default=None, min_length=1, max_length=120)
    is_active: bool | None = None


class WidgetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # lets it read off the model

    id: uuid.UUID
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class WidgetPage(BaseModel):
    items: list[WidgetRead]
    total: int
    limit: int
    offset: int
```

### 3. Repository — `src/api_base/widget/repository.py`

```python
"""Layer: repository. All SQL for widgets. Returns models or None, never raises HTTP."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api_base.repository import BaseRepository
from api_base.widget.model import Widget


class WidgetRepository(BaseRepository[Widget]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Widget, session)

    async def get_by_name(self, name: str) -> Widget | None:
        return await self.session.scalar(
            select(Widget).where(func.lower(Widget.name) == name.lower())
        )
```

`BaseRepository` already gives you `get`, `get_many`, `create`, `update`,
`delete`, and `count`, typed to `Widget`. Add only what it does not cover. If
this file is short, you did it right.

### 4. Service — `src/api_base/widget/service.py`

```python
"""Layer: service. All business rules for widgets. No SQL, no HTTPException."""

import uuid

from api_base.exceptions import ConflictError, NotFoundError
from api_base.widget.repository import WidgetRepository
from api_base.widget.schema import WidgetCreate, WidgetPage, WidgetRead


class WidgetService:
    def __init__(self, repository: WidgetRepository) -> None:
        self.repository = repository

    async def get(self, widget_id: uuid.UUID) -> WidgetRead:
        widget = await self.repository.get(widget_id)
        if widget is None:
            raise NotFoundError(f"No widget with id {widget_id}.")
        return WidgetRead.model_validate(widget)

    async def create(self, payload: WidgetCreate) -> WidgetRead:
        name = " ".join(payload.name.split())
        if await self.repository.get_by_name(name) is not None:
            raise ConflictError(f"A widget named {name!r} already exists.")
        widget = await self.repository.create({"name": name, "is_active": payload.is_active})
        return WidgetRead.model_validate(widget)

    async def list_widgets(self, *, limit: int = 50, offset: int = 0) -> WidgetPage:
        widgets = await self.repository.get_many(limit=limit, offset=offset)
        return WidgetPage(
            items=[WidgetRead.model_validate(w) for w in widgets],
            total=await self.repository.count(),
            limit=limit,
            offset=offset,
        )
```

### 5. Wiring — `src/api_base/widget/dependencies.py`

```python
"""Wiring for this feature -- no logic."""

from typing import Annotated

from fastapi import Depends

from api_base.dependencies import SessionDep
from api_base.widget.repository import WidgetRepository
from api_base.widget.service import WidgetService


def get_widget_repository(session: SessionDep) -> WidgetRepository:
    return WidgetRepository(session)


WidgetRepositoryDep = Annotated[WidgetRepository, Depends(get_widget_repository)]


def get_widget_service(repository: WidgetRepositoryDep) -> WidgetService:
    return WidgetService(repository)


WidgetServiceDep = Annotated[WidgetService, Depends(get_widget_service)]
```

### 6. Router — `src/api_base/routers/widget.py`

Note this one lives in `routers/`, next to every other HTTP surface.

```python
"""Layer: router. Schema binding, status codes, and one service call each."""

import uuid

from fastapi import APIRouter, Query, status

from api_base.widget.dependencies import WidgetServiceDep
from api_base.widget.schema import WidgetCreate, WidgetPage, WidgetRead

router = APIRouter(prefix="/widgets", tags=["widgets"])


@router.post(
    "", response_model=WidgetRead, status_code=status.HTTP_201_CREATED, summary="Create a widget"
)
async def create_widget(payload: WidgetCreate, service: WidgetServiceDep) -> WidgetRead:
    return await service.create(payload)


@router.get("", response_model=WidgetPage, summary="List widgets")
async def list_widgets(
    service: WidgetServiceDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> WidgetPage:
    return await service.list_widgets(limit=limit, offset=offset)


@router.get("/{widget_id}", response_model=WidgetRead, summary="Get a widget")
async def get_widget(widget_id: uuid.UUID, service: WidgetServiceDep) -> WidgetRead:
    return await service.get(widget_id)
```

No `try`/`except`. The handlers in `exceptions.py` turn the domain errors into
responses.

### 7. Register the router — `src/api_base/main.py`

```python
from api_base.routers.widget import router as widget_router

# inside create_app(), next to the other include_router calls
app.include_router(widget_router, prefix=settings.api_prefix)
```

### 8. Create the table

The migration that creates `widgets` belongs in the migrations repository, not
here — see [Migrations](#migrations). The model above only describes a table
this service expects to already exist.

### 9. Test

Two files, mirroring `tests/test_item_api.py` and `tests/test_item_service.py`:
the router over HTTP with the `client` fixture, and the service against a stub
repository with no database at all.

---

## Migrations

**This repository does not own the database schema.** There are no migrations
here and no migration tool in the dependencies. Schema changes live in a
separate migrations repository and are applied there, before this service
starts.

What that means day to day:

- The SQLAlchemy models in `src/api_base/*/model.py` describe tables this
  service expects to already exist. Adding a model does not create a table.
- A model change and the matching migration are two commits in two
  repositories. Ship the migration first — a column the service reads but the
  database does not have is an outage; a column the database has but the
  service ignores is not.
- The naming convention in `db.py` is there so the constraint names in these
  models match the ones the migrations repository creates.
- `docker compose up` starts Postgres and the API and nothing else. For local
  work, apply the migrations repository against `localhost:5432` yourself.

The test suite is unaffected: `tests/conftest.py` builds the schema with
`Base.metadata.create_all` and drops it at the end, so tests never need a
migration to run.

---

## Configuration

Every setting in `config.py` reads from the environment first and `.env`
second. See `.env.example` for the full list.

| Variable | Default | Notes |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/api_base` | Must use an async driver |
| `APP_NAME` | `api-base` | Shown in OpenAPI and the liveness probe |
| `ENVIRONMENT` | `local` | `local`, `test`, `staging`, `production` |
| `DEBUG` | `false` | Also turns on SQLAlchemy echo |
| `LOG_LEVEL` | `INFO` | Applied to the root and uvicorn loggers |
| `API_PREFIX` | `/api/v1` | All routers mount under this |
| `CORS_ORIGINS` | `[]` | JSON array or comma-separated; middleware is skipped if empty |
| `TEST_DATABASE_URL` | `...@localhost:5432/api_base_test` | Test suite only |

## Endpoints

| Method | Path | |
| --- | --- | --- |
| GET | `/api/v1/health/live` | Liveness; never touches the database |
| GET | `/api/v1/health/ready` | Readiness; 503 if the database is unreachable |
| POST | `/api/v1/items` | 201, 409 on a duplicate name |
| GET | `/api/v1/items` | `?limit=&offset=&is_active=` |
| GET | `/api/v1/items/{id}` | 404 if absent |
| PATCH | `/api/v1/items/{id}` | Only the fields sent are changed |
| DELETE | `/api/v1/items/{id}` | 204 |
