import pytest

pytest.importorskip("pgembed")

import psycopg2

from genesis.local import postgres


def test_start_creates_database_and_runs_query(tmp_path, monkeypatch):
    monkeypatch.setattr(postgres, "DATA_DIR", tmp_path / "postgres")
    monkeypatch.setenv("POSTGRES_DB", "genesis_test")
    monkeypatch.setenv("POSTGRES_USER", "genesis_test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "genesis_test")

    params = postgres.start()
    try:
        conn = psycopg2.connect(**params)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                assert cur.fetchone() == (1,)
                cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
                assert cur.fetchone() == (1,)
        finally:
            conn.close()
    finally:
        postgres.stop()
