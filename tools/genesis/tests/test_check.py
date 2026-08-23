from genesis_cli.cli import _live_schema, _types_match

SCHEMA = {"components": {"schemas": {"ItemRead": {}, "ChatResponse": {}}}}


def test_types_match_when_every_schema_is_present():
    generated = 'export interface components { schemas: { ItemRead: {}, ChatResponse: {} } }'
    assert _types_match(generated, SCHEMA) is True


def test_types_are_stale_when_a_schema_is_missing():
    generated = "export interface components { schemas: { ItemRead: {} } }"
    assert _types_match(generated, SCHEMA) is False


def test_schemaless_document_matches_trivially():
    assert _types_match("", {"components": {"schemas": {}}}) is True
    assert _types_match("", {}) is True


def test_live_schema_returns_none_when_unreachable():
    assert _live_schema("http://127.0.0.1:9/openapi.json") is None


def test_live_schema_returns_none_on_garbage(monkeypatch):
    assert _live_schema("not-a-url") is None
