import duckdb

from genesis.core.config import POSTGRES


def _libpq_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def _pg_dsn() -> str:
    fields = {
        "host": POSTGRES["host"],
        "port": str(POSTGRES["port"]),
        "dbname": POSTGRES["database"],
        "user": POSTGRES["user"],
        "password": POSTGRES["password"],
    }
    return " ".join(f"{key}={_libpq_value(value)}" for key, value in fields.items())


def check() -> bool:
    try:
        duckdb.connect().close()
        return True
    except Exception:
        return False


def query(sql: str) -> list[dict]:
    con = duckdb.connect()
    try:
        con.execute("LOAD postgres")
        dsn_as_sql_literal = _pg_dsn().replace("'", "''")
        con.execute(f"ATTACH '{dsn_as_sql_literal}' AS pg (TYPE postgres, READ_ONLY)")
        cursor = con.execute(sql)
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        con.close()
