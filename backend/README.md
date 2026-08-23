# Genesis backend

FastAPI service. See the [root README](../README.md) for the full picture.

```bash
uv sync
ENV_FOR_DYNACONF=development uv run uvicorn genesis.main:app --reload --port 8000
```

Requires Postgres and whatever installed modules need (Valkey, Temporal) reachable at the
addresses `genesis/core/config.py` resolves — all provided by the container from `genesis dev`.
