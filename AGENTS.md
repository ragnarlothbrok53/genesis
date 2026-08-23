<system_instructions>
  <role>
    You are a pragmatic, senior software engineer who values simplicity, readability, and immediate functional utility over clever abstractions.
  </role>

  <code_style_rules>
    <rule_1>
      NO COMMENTS: Do not write code comments, docstrings, or inline explanations. 
      The code must be completely self-documenting through clear, intent-driven naming. 
      Only allow a comment if it explains a bizarre, non-obvious third-party bug or a hardware invariant.
    </rule_1>

    <rule_2>
      ANTI-OVERENGINEERING: Do not build features, abstractions, or "extensions" beyond the immediate scope of the request.
      Do not implement generic types, interfaces, or factories unless they are explicitly required for the current task.
    </rule_2>

    <rule_3>
      PREFER STANDARD LIBRARIES: Consolidate verbose logic into native standard library implementations. 
      Do not install external packages for simple utility logic.
    </rule_3>

    <rule_4>
      FLAT OVER NESTED: Write simple, straightforward control flows. 
      Use early returns and guard clauses to keep indentation shallow. Avoid deep nested conditionals.
    </rule_4>
    
    <rule_5>
      NO "AI SLOP": Remove redundant defensive null/undefined checks that are already guaranteed by the type system or environment.
    </rule_5>
  </code_style_rules>

  <output_formatting>
    Do not add conversational fluff or theoretical summaries before or after code blocks. 
    Output the requested code changes directly.
  </output_formatting>
</system_instructions>

---

# What is this repo

Genesis is a starter template for small full-stack web apps. It ships as **one Docker
container** that runs everything: a React web page, a Python API, a database, a cache, a
background-job engine, and dashboards. You build features by copying the examples that are
already here.

Two words worth knowing:

- **Endpoint** — one URL the web page calls to get or change data (for example
  `/api/v1/items`). Endpoints live in `backend/app/api/v1/`.
- **Model** — one database table, described as a Python class (for example `Item`). Models
  live in `backend/app/models/`.

## Run it

One CLI runs everything: **`genesis`**. `manage.cmd` / `./manage.sh` forward to it, so either spelling works.

- `genesis dev` — build and start at http://localhost:8000 (`--no-build` to skip the rebuild)
- `genesis down` — stop · `genesis logs` — follow logs · `genesis restart [proc]` — reload one process
- `genesis migrate "msg"` — create + apply a migration after a model change
- `genesis map` — print the resolved graph (routes, tables, tasks, pages) without starting the app
- `genesis docs` — regenerate the AI context documents · `genesis check` — fail if they are stale
- `genesis create my-app --preset saas` — create a new project (`genesis presets` lists them)
- `genesis add jobs` / `genesis remove jobs` — add or remove a module in the current project
- `genesis generate scaffold Item name:string price:float` — model + endpoint + page in one shot
  (`generate model` / `generate endpoint` / `generate page` do just one piece; `g` is a shorthand
  alias for `generate`). Field types: `string text int float bool datetime`, suffix `?` for
  nullable. Use `user:references` (or `author:references:User` when the field name doesn't match
  the model) for a foreign key — the target model must already exist. A reference always flattens
  to its id (`user: int`) in every shape and in every API response, never a nested object.
- `genesis destroy scaffold Item` — the reverse: deletes the model, endpoint and page a scaffold
  created (`destroy model` / `endpoint` / `page` for just one piece; `d` is a shorthand alias).
- `genesis generate logger backend/app/tasks/reports.py` — add `logging.getLogger(__name__)`
  boilerplate to an existing file; safe to run again (no-op if it already has one).
- `genesis render --out DIR --without jobs` — assemble a project without creating `.env` or docs
- Running `manage` with no arguments launches an **interactive** setup wizard (humans only; it hangs in a non-interactive shell).

Two rules when iterating:

- **Backend code is bind-mounted** — after editing `backend/**`, reload in seconds with
  `docker exec genesis-app_dev-1 supervisorctl restart fastapi`.
  or `genesis restart`.
  <!-- >>> module:jobs -->
  Also `genesis restart temporal-worker` if you touched `genesis/services/jobs.py` or `app/tasks/`.
  <!-- <<< module:jobs -->
  Only `genesis dev` (full rebuild) for dependency/Dockerfile/deploy changes.
- **`.env` is applied at container-create** — after editing it, run
  `docker compose --profile dev up -d --force-recreate`, not a process restart.

Full operational detail lives in the `manage` skill at `.claude/skills/manage/SKILL.md`.

## Architecture map

The web page (frontend) talks to the API (backend). Every request flows the same way:

```
frontend (React)  ->  app/endpoints/<feature>.py  ->  genesis facade  ->  app/models/ (database)
   pages/*.tsx           the endpoint                  db · jobs · ai …    one table
```

You write files under `backend/app/` and `frontend/src/pages/`; everything auto-wires by
convention — **no registration lists to edit**.

**The naming law — the path tells you what a file is:**

| Path | Means |
| --- | --- |
| `app/models/item.py` | table `items`, class `Item`, plus `ItemCreate` / `ItemRead` |
| `app/models/chat.py` | shapes only (`ChatRequest`, `ChatResponse`) — no table |
| `app/endpoints/items.py` | `/api/v1/items` (from `api = router("/items")`) |
| `app/tasks/reports.py` | `@task` functions on the worker |
| `frontend/src/pages/Items.tsx` | route `/items`, nav entry "Items" |

**Every data shape lives in `app/models/<concept>.py`** — whether or not a table backs it.
Endpoints contain routing only: no Pydantic classes, ever. There is no shared `schemas.py`.
(The kernel's own endpoints in `genesis/main.py` define their shapes inline; that file is
infrastructure and not yours to edit.)

- `backend/app/endpoints/<feature>.py` — drop a file that defines `api = router(...)`; it
  auto-mounts. Thin: read the request, call the model or facade, return the result.
- `backend/app/models/<name>.py` — one file per table (a `db.Model`) **and its request
  shapes**. Auto-discovered. Connection opened/closed per request for you.
- `backend/app/tasks/<name>.py` — `@task` functions; auto-registered on the worker.
- `frontend/src/pages/<Name>.tsx` — one page per file; auto-routes from its `route`/`nav` exports.
- `backend/genesis/` — the facade you import from (don't edit). `genesis/core` (kernel) and
  `genesis/services` (swappable modules) are the plumbing behind it.

### The facade (import from `genesis`, nothing lower-level)

```python
from genesis import db         # db.Model · db.Text/Char/Int/Float/Bool/DateTime/FK · db.now · db.to_dict
from genesis import jobs       # jobs.run_task(fn, *args) · jobs.job_status(id)
from genesis import ai         # ai.chat(prompt, system=None) -> str · ai.complete(messages)
from genesis import cache      # cache.get_json(key) · cache.set_json(key, val) · cache.delete(key)
from genesis import analytics  # analytics.query(sql) -> list[dict], tables as pg.public.<table>
from genesis import auth, router, task, run_task, job_status, settings
```

Models are **Peewee** (`Item.select().where(Item.name == "x")`). Return rows with `.dicts()`
and single rows with `db.to_dict(obj)` — no separate response schema to maintain.

Telemetry (logs, traces, metrics) is automatic. You never write telemetry code.

---

# Recipes

Each recipe clones something that already works. Copy the referenced file, rename, adjust.

## Add an endpoint

Drop a file in `backend/app/endpoints/` that defines `api = router(...)`. **That's it — it
auto-registers.** There is no list to edit.

```python
from fastapi import HTTPException

from app.models.item import Item, ItemCreate, ItemRead
from genesis import db, router

api = router("/items")


@api.get("", response_model=list[ItemRead])
def list_items():
    return list(Item.select().order_by(Item.id).dicts())


@api.post("", response_model=ItemRead, status_code=201)
def create_item(payload: ItemCreate):
    return db.to_dict(Item.create(**payload.model_dump()))


@api.delete("/{item_id}", status_code=204)
def delete_item(item_id: int):
    if not Item.delete_by_id(item_id):
        raise HTTPException(status_code=404, detail="Item not found")
```

**Every endpoint declares `response_model`.** That is what keeps the OpenAPI schema complete,
which is what the frontend generates its types from — so an untyped endpoint silently costs
the frontend its type safety.

It's live at `/api/v1/items`. On startup the app logs what it wired
(`genesis: wired N models, M endpoints`).

## Add a DB model

Drop a file in `backend/app/models/`. It's **auto-discovered** — no registration. (`db.Model`
gives an auto `id` primary key.)

```python
from pydantic import BaseModel, Field

from genesis import db


class Widget(db.Model):
    name = db.Char(max_length=200)
    quantity = db.Int(default=1)
    created_at = db.DateTime(default=db.now)

    class Meta:
        table_name = "widgets"


class WidgetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    quantity: int = 1


class WidgetRead(BaseModel):
    id: int
    name: str
    quantity: int
```

If the model belongs to a **module**, list its generated `backend/migrations/NNN_*.py` in that
module's `module.toml` under `files`, so removing the module removes its table too.

Everything about one concept lives in one file: the table, the create shape, the read shape.
Endpoints return rows straight from the database with `.dicts()` / `db.to_dict`, and the
`Read` shape types the response. Then create + apply the migration (never hand-write
DDL): `genesis migrate "add widgets"`.

<!-- >>> module:jobs -->
## Add a background job

Jobs are durable and run in the background. You write a plain function; the engine handles
retries and persistence.

1. Drop a file in `backend/app/tasks/` with a `@task` function — **auto-registered** on the worker:

```python
from genesis import task


@task
def summarize_items(count: int) -> str:
    return f"processed {count} items"
```

2. Start it from any endpoint and read its status:

```python
from genesis import jobs
from app.tasks.reports import summarize_items

job_id = await jobs.run_task(summarize_items, 42)
status = await jobs.job_status(job_id)
```

<!-- <<< module:jobs -->
## Add explicit logging

Telemetry is automatic (see above) — this is for the log lines *you* choose to write, e.g.
"order #%s shipped to %s". Plain stdlib `logging` already flows through the same OTel pipeline
as everything else, so a `logger.info(...)` call gets full trace correlation for free.

`genesis generate logger <file>` drops the boilerplate into an existing file — a model,
endpoint or task — and is safe to run more than once:

```
genesis generate logger backend/app/tasks/reports.py
```

```python
import logging

from genesis import task

logger = logging.getLogger(__name__)


@task
def summarize_items(count: int) -> str:
    return f"processed {count} items"
```

Add the `logger.info(...)` / `logger.warning(...)` calls yourself at the points worth naming —
the generator only wires the logger, it doesn't guess what's worth logging.

## Add a frontend page

Drop a file in `frontend/src/pages/`. It **auto-routes** — no `App.tsx` or `Layout.tsx` edits.
Export a default component plus `route` (and optionally `nav` to appear in the top navigation):

```tsx
import { LayoutGrid } from "lucide-react"

export const route = "/widgets"
export const nav = { label: "Widgets", icon: LayoutGrid, order: 4 }

export default function Widgets() {
  return <div>Widgets</div>
}
```

Call the API with the client in `frontend/src/lib/api.ts` (`api.get`, `api.post`, `api.del`).

**Never hand-write a type for an API shape.** `src/lib/api-types.ts` is generated from the
backend's OpenAPI schema; reference it through the `Schema` helper:

```tsx
import { api, type Schema } from "@/lib/api"

type Item = Schema<"ItemRead">

const items = await api.get<Item[]>("/api/v1/items")
```

`npm run dev` regenerates the types first, so a running backend keeps them current. If you
change a model while the dev server is already running, run `npm run types`.

## Add an LLM / cache / analytics call

```python
from genesis import ai, analytics, cache

reply = ai.chat("Summarize this in one line: ...", system="You are terse.")

cache.set_json("last_reply", {"text": reply})
cached = cache.get_json("last_reply")

rows = analytics.query("SELECT count(*) AS n FROM pg.public.items")
```

The LLM provider is chosen by `LLM_MODEL` in `.env` (e.g. `anthropic/claude-sonnet-4`,
`google/gemini-2.5-pro`) — one gateway key reaches all of them. For full control (message
history, temperature, etc.) use `ai.complete(messages, temperature=0.2)`.

See `backend/app/endpoints/ai.py` and `backend/app/endpoints/analytics.py` for working endpoints.

---

# DO NOT EDIT

These are infrastructure. Changing them breaks the build or the container. Leave them alone
unless the user explicitly asks:

- `deploy/**` (nginx, supervisord, entrypoint)
- `Dockerfile`
- `docker-compose.yml`
- `manage.sh` / `manage.ps1`
- `backend/genesis/**` (the facade, kernel, loader, and service modules)
- `backend/genesis/**` (the facade + auto-loader you import from)
- `backend/settings.toml`

Configuration goes in `.env` only (about 5 knobs). Everything else is locked or derived.

---

# Definition of done

Before you consider a change finished, it must pass:

- Backend: `cd backend && uvx ruff check .`
- Frontend: `cd frontend && npm run build`
- Generated files: `genesis check` (fails if the AI context documents or `genesis.json` are stale)

Use `uvx ruff`, not `uv run ruff` — the latter syncs the whole project first, which fails on
Windows because `litellm` ships a Rust extension with no prebuilt wheel.

If you changed a model or an endpoint signature, regenerate the frontend types
(`cd frontend && npm run types`, with the app running) and commit `src/lib/api-types.ts`
alongside the backend change.

Schema changes are versioned with **peewee-migrate** — migration files live in
`backend/migrations/`. Never hand-write `CREATE TABLE` / `ALTER TABLE` SQL and never edit the
database by hand. After changing or adding a model, run `genesis migrate "msg"` to generate the
migration; the app applies pending migrations automatically on startup.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:970c3bf2 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `bd` for task tracking. Do not run git commits, git pushes, or Dolt remote sync unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close beads, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   bd dolt push
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END BEADS INTEGRATION -->

<!-- BEGIN BEADS CODEX SETUP: generated by bd setup codex -->
## Beads Issue Tracker

Use Beads (`bd`) for durable task tracking in repositories that include it. Use the `beads` skill at `.agents/skills/beads/SKILL.md` (project install) or `~/.agents/skills/beads/SKILL.md` (global install) for Beads workflow guidance, then use the `bd` CLI for issue operations.

### Quick Reference

```bash
bd ready                # Find available work
bd show <id>            # View issue details
bd update <id> --claim  # Claim work
bd close <id>           # Complete work
bd prime                # Refresh Beads context
```

### Rules

- Use `bd` for all task tracking; do not create markdown TODO lists.
- Run `bd prime` when Beads context is missing or stale. Codex 0.129.0+ can load Beads context automatically through native hooks; use `/hooks` to inspect or toggle them.
- Keep persistent project memory in Beads via `bd remember`; do not create ad hoc memory files.

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.
<!-- END BEADS CODEX SETUP -->
