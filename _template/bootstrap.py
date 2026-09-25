#!/usr/bin/env python3
"""One-shot rename script for a repo created from the api-base template.

Run it once, from the repository root, before installing anything:

    python bootstrap.py my-new-api

It renames the package, rewrites every reference to the template name, replaces
this README with a project README, deletes itself, and stages the result. Only
the standard library is used, so it works on a bare Python 3.12 with no venv.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

TEMPLATE_PROJECT = "api-base"
TEMPLATE_PACKAGE = "api_base"

NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")

# Extensions rewritten in place, plus a few files matched by exact name.
REWRITE_SUFFIXES = {".py", ".toml", ".md", ".yml", ".yaml", ".ini"}
REWRITE_NAMES = {"Dockerfile", ".env.example"}

SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules"}
SKIP_FILES = {"uv.lock", "poetry.lock", "package-lock.json", "requirements.txt", "bootstrap.py"}

ROOT = Path(__file__).resolve().parent

README = """\
# {project}

A FastAPI service.

## Structure

Code is grouped by feature. Everything about one entity lives in one folder:

    src/{package}/
      main.py, config.py, db.py, repository.py, exceptions.py, dependencies.py
      item/          model.py, schema.py, repository.py, service.py, dependencies.py
      routers/       every HTTP surface, together

Routers are the exception to feature grouping, so the whole API can be read in
one place.

## Layering

    router -> service -> repository -> model

Each layer talks only to the one below it. Routers never touch the session or a
SQLAlchemy model. Services never write SQL and never raise `HTTPException` --
they raise the domain errors in `exceptions.py`. Repositories return models or
`None`; deciding that "no row" means 404 is the service's job. Models never
leave their feature package.

A model is the table; a schema is the API contract. They are separate classes
on purpose, because the two shapes diverge.

## Run it

```bash
uv sync                    # create .venv and install
cp .env.example .env       # then edit DATABASE_URL
docker compose up -d db    # Postgres on :5432
uv run uvicorn {package}.main:app --reload
```

Docs at http://localhost:8000/docs.

Or run everything in containers:

```bash
docker compose up --build
```

## Checks

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
uv run pre-commit install   # once, to run the above on every commit
```

## Migrations

This repository does not own the database schema. Migrations live in a separate
repository and are applied there, before this service starts. A model here
describes a table that is expected to already exist -- adding one does not
create it. Ship the migration first, then the model change.

Tests are unaffected: `tests/conftest.py` builds the schema with
`Base.metadata.create_all` and drops it afterwards.

## Adding a feature

Copy `src/{package}/item/` and work bottom up. In `src/{package}/<feature>/`:

1. `model.py` -- subclass `TimestampedBase` (id, created_at, updated_at).
2. `schema.py` -- `Create`, `Update`, `Read`, `Page`.
3. `repository.py` -- subclass `BaseRepository[Model]`; add only the queries the
   base class does not already cover.
4. `service.py` -- take the repository in `__init__`, apply the rules, return
   schemas, raise from `exceptions.py`.
5. `dependencies.py` -- providers for the repository and the service.

Then `src/{package}/routers/<feature>.py` (one service call per endpoint, each
with a `response_model`, a `summary`, and a tag), and register the router in
`main.py`. The migration that creates the table goes in the migrations
repository.
"""


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def read_project_name() -> str:
    if len(sys.argv) > 2:
        fail("usage: python bootstrap.py <project-name>")
    name = sys.argv[1] if len(sys.argv) == 2 else input("Project name (lowercase-with-dashes): ")
    name = name.strip()
    if not NAME_PATTERN.match(name):
        fail(
            f"{name!r} is not a valid project name. Use lowercase letters, digits, and single "
            "dashes between words, starting with a letter -- for example 'billing-api'."
        )
    return name


def iter_rewritable_files() -> list[Path]:
    files: list[Path] = []
    for path in sorted(ROOT.rglob("*")):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        if not path.is_file() or path.name in SKIP_FILES:
            continue
        if path.suffix in REWRITE_SUFFIXES or path.name in REWRITE_NAMES:
            files.append(path)
    return files


def rename_package(package: str) -> None:
    source = ROOT / "src" / TEMPLATE_PACKAGE
    target = ROOT / "src" / package
    if package == TEMPLATE_PACKAGE:
        print(f"  keep    src/{TEMPLATE_PACKAGE}/ (name unchanged)")
        return
    if not source.is_dir():
        fail(f"src/{TEMPLATE_PACKAGE}/ not found -- has bootstrap already run?")
    if target.exists():
        fail(f"src/{package}/ already exists")
    source.rename(target)
    print(f"  rename  src/{TEMPLATE_PACKAGE}/ -> src/{package}/")


def rewrite_files(project: str, package: str) -> None:
    for path in iter_rewritable_files():
        original = path.read_text(encoding="utf-8")
        updated = original.replace(TEMPLATE_PACKAGE, package).replace(TEMPLATE_PROJECT, project)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            print(f"  rewrite {path.relative_to(ROOT)}")


def rewrite_lock(project: str) -> None:
    """Rename just the root package entry in uv.lock.

    The bulk rewrite skips lock files on purpose -- they are generated, and a
    blind search-and-replace across pinned package names is a good way to
    corrupt one. But the lock records this project under its own name, and
    `uv sync --frozen` (used by the Dockerfile and by CI) fails if that name no
    longer matches pyproject.toml. So patch exactly that one line.
    """
    lock = ROOT / "uv.lock"
    if not lock.is_file() or project == TEMPLATE_PROJECT:
        return

    blocks = lock.read_text(encoding="utf-8").split("[[package]]")
    for index, block in enumerate(blocks):
        if 'source = { editable = "." }' in block:
            blocks[index] = block.replace(f'name = "{TEMPLATE_PROJECT}"', f'name = "{project}"', 1)
            lock.write_text("[[package]]".join(blocks), encoding="utf-8")
            print("  rewrite uv.lock (root package name only)")
            return


def write_readme(project: str, package: str) -> None:
    (ROOT / "README.md").write_text(README.format(project=project, package=package), "utf-8")
    print("  replace README.md")


def delete_self() -> None:
    Path(__file__).resolve().unlink()
    print("  delete  bootstrap.py")


def git_add() -> None:
    if not (ROOT / ".git").exists():
        print("  skip    git add -A (not a git repository)")
        return
    result = subprocess.run(["git", "add", "-A"], cwd=ROOT)
    if result.returncode != 0:
        print("  warn    git add -A failed; stage the changes yourself")
        return
    print("  run     git add -A")


def main() -> None:
    project = read_project_name()
    package = project.replace("-", "_")

    print(f"Bootstrapping {project!r} (package {package!r})")
    rename_package(package)
    rewrite_files(project, package)
    rewrite_lock(project)
    write_readme(project, package)
    delete_self()
    git_add()

    print(
        "\nDone. Next:\n"
        "  uv sync\n"
        "  cp .env.example .env\n"
        "  docker compose up -d db\n"
        f"  uv run uvicorn {package}.main:app --reload\n"
        '\nThen commit: git commit -m "Initial commit"'
    )


if __name__ == "__main__":
    main()
