# Genesis

A starter template for small full-stack web apps. You get a working app out of the box — a web
page, an API, a database, a cache, background jobs, and dashboards — all inside **one Docker
container**. You build your app by copying the examples that are already here (or by telling an
AI assistant "add X" — see the tutorial below).

Two words that show up a lot:

- **Container** — a self-contained box that runs the whole app on your machine. You start it
  with one command; you don't install Python, Postgres, or anything else by hand.
- **Endpoint** — one URL the web page calls to get or save data, e.g. `/api/v1/items`.

## What you'll see

When it's running, open **http://localhost:8000** and you get a demo app that already does the
full round-trip: add items to a database, run a background job, ask an LLM a question, and view
analytics.

---

## Requirements

- **A container runtime**, installed and **running** — any one of:
  - [**Rancher Desktop**](https://rancherdesktop.io) — free for company use (recommended at work)
  - [**Docker Desktop**](https://www.docker.com/products/docker-desktop) — free for personal use (paid for larger companies)
  - [**OrbStack**](https://orbstack.dev) — Mac only, fastest
  - Give it at least **4 GB RAM** (6 GB is comfortable), **2 CPUs**, **~5 GB free disk**.
- **git** (to clone this repo).
- **Node.js** — only if you want live frontend editing (optional; see below). Not needed to run
  the app.

Don't worry about getting this exactly right — the guided setup checks all of it and tells you
what's missing with links.

The **first build takes about 3-5 minutes** while Docker downloads and assembles everything.
After that, starts are fast.

---

## Quickstart

Clone the repo, then run **one command with no arguments** from the project folder — it
launches a guided setup that checks Docker, sets up your `.env`, and starts the app for you.

**Windows:** double-click `manage.cmd`, or run:

```bat
manage.cmd
```

**macOS / Linux:**

```bash
./manage.sh
```

Answer the few prompts (app name, optional AI key, and it auto-fills the rest). When it
finishes it opens at **http://localhost:8000**.

That's the whole setup. No config files to hand-edit, no execution-policy fiddling. The guided
setup also grabs your company's certificate automatically if you're on a corporate network.

To stop it later: `manage.cmd down` (Windows) or `./manage.sh down` (macOS/Linux). To start it
again without the wizard: `manage.cmd dev`.

### Live frontend editing (optional)

For instant reloads while editing the web page, run Vite locally against the running container:

```bash
cd frontend && npm install && npm run dev   # http://localhost:5173
```

### Installing the `genesis` CLI standalone

`manage.cmd` / `./manage.sh` cover everything above with zero setup. If you'd rather have
`genesis` on your PATH directly, the only prerequisite is
[**uv**](https://docs.astral.sh/uv/getting-started/installation/) — no local Python required:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh      # macOS/Linux
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"   # Windows
```

Then install the CLI straight from this repo:

```bash
uv tool install --from tools/genesis genesis-cli
```

`genesis dev`, `genesis migrate`, `genesis generate ...` now work from anywhere inside this
repo (or any project `genesis create` produced).

---

## Routes

Everything is served from **http://localhost:8000**.

**Core (your app):**

| Route     | What it is                          |
| --------- | ----------------------------------- |
| `/`       | The app (the React web page)        |
| `/admin`  | Admin page (role-gated)             |
| `/status` | Health / status page                |

**Advanced tools (built in, for when you need them):**

| Route        | What it is                              |
| ------------ | --------------------------------------- |
| `/db`        | Database dashboard (browse + run queries) |
<!-- >>> module:jobs -->
| `/temporal/` | Background-job engine dashboard         |
<!-- <<< module:jobs -->
| `/o11y`      | Logs, traces, and metrics dashboard     |

---

## Your first change (tutorial)

Let's add a **`quantity`** number to Items and show it end-to-end. This touches every layer,
so once you've done it you understand the whole template.

### 1. Add the field to the database model

`backend/app/models/item.py` — add a field to the `Item` class (and import `IntegerField`
at the top from `peewee`):

```python
quantity = IntegerField(default=1)
```

### 2. Add it to the request shape

Same file — `ItemCreate` lives right below the model. Add `quantity` to it:

```python
class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    quantity: int = 1
```

Add it to `ItemRead` too — that shape types the response and feeds the generated frontend
types. You do **not** edit the endpoint; `list_items` returns the row straight from the
database.

### 3. Apply the change to the database

Run the migrate command — it writes a versioned migration file into the repo (by diffing
your models) and applies it:

```bash
genesis migrate "add quantity"
```

Migrations are handled by **peewee-migrate**, and any pending migration is applied
automatically every time the app starts — so a teammate who pulls your change just runs
`dev` and their database updates itself. You never edit the database by hand.

### 4. Show it on the web page

First refresh the generated types, then edit the page:

```bash
cd frontend && npm run types    # regenerates src/lib/api-types.ts from the running API
```

`frontend/src/pages/Items.tsx` — the `Item` type already knows about `quantity`, so you only
touch the UI:

- Send it when adding: in `add()`, include it in the POST body,
  e.g. `api.post("/api/v1/items", { name, quantity })`.
- Add a `Quantity` column to the table (a `<TableHead>` in the header and a
  `<TableCell>{item.quantity}</TableCell>` in each row).

Reload http://localhost:8000 and your items now carry a quantity.

<!-- >>> module:jobs -->
### Bonus: add a background job

Some work shouldn't block the web page (sending email, crunching numbers). Use a background
job. Drop a file in `backend/app/tasks/` — it registers itself:

```python
from genesis import task


@task
def restock_report(item_count: int) -> str:
    return f"reported on {item_count} items"
```

Start it from any endpoint and check on it later:

```python
from genesis import jobs
from app.tasks.restock import restock_report

job_id = await jobs.run_task(restock_report, 10)
status = await jobs.job_status(job_id)
```

That's the whole pattern: write a normal function, `run_task` it, `job_status` to check.

> Deeper "how to extend" recipes for an AI assistant live in `CLAUDE.md`.

---
<!-- <<< module:jobs -->

## Config

You only ever edit **`.env`** (copy `.env.example` to `.env` first). It has about 5 knobs:

| Knob                | What it's for                          |
| ------------------- | -------------------------------------- |
| `APP_NAME`          | The name shown in the app              |
<!-- >>> module:ai -->
| `LLM_API_KEY`       | Your LLM key (needed for the chat demo)|
| `LLM_BASE_URL`      | LLM gateway (OpenRouter / Portkey / any OpenAI-compatible) |
| `LLM_MODEL`         | Which model to use — switch provider by changing this |
<!-- <<< module:ai -->
| `POSTGRES_PASSWORD` | Database password                      |
| `O2_ROOT_PASSWORD`  | Dashboard admin password               |

**One key, every provider.** The chat demo uses a gateway, so a single `LLM_API_KEY`
reaches Anthropic, OpenAI, Gemini, and more — you switch provider by changing `LLM_MODEL`
(e.g. `anthropic/claude-sonnet-4`, `google/gemini-2.5-pro`, `openai/gpt-4o-mini`).

Everything else is locked or derived. Do not edit `backend/settings.toml`, the `Dockerfile`,
`docker-compose.yml`, the `deploy/` folder, or `backend/genesis/` — those are infrastructure.

---

## Corporate networks (TLS interception)

If your network runs a TLS-intercepting proxy, image builds can fail on certificate
verification. **You don't need to do anything manually** — the guided setup offers to grab your
company's certificate for you, or you can run `manage.cmd certs` (Windows) / `./manage.sh certs`
(macOS/Linux) any time. It saves the certificate into `deploy/certs/`, which the build trusts
automatically. `.crt` files are gitignored, and on a normal network this stays empty and is a
no-op.
