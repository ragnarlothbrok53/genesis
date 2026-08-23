import pytest

from genesis_cli import ux
from genesis_cli.fields import parse_fields


class _FakeQuestion:
    def __init__(self, value=None, raise_exc=None):
        self._value = value
        self._raise_exc = raise_exc

    def unsafe_ask(self):
        if self._raise_exc:
            raise self._raise_exc
        return self._value


def _force_tty(monkeypatch, value=True):
    monkeypatch.setattr(ux.sys.stdin, "isatty", lambda: value)
    monkeypatch.setattr(ux.sys.stdout, "isatty", lambda: value)


def test_success_error_warning_info_do_not_crash(capsys):
    ux.success("ok")
    ux.error("bad")
    ux.warning("careful")
    ux.info("fyi")
    out = capsys.readouterr()
    assert "ok" in out.out
    assert "careful" in out.out
    assert "fyi" in out.out
    assert "bad" in out.err


def test_table_prints_headers_and_rows(capsys):
    ux.table(["name", "type"], [["title", "string"], ["price", "float"]])
    out = capsys.readouterr().out
    assert "name" in out
    assert "title" in out
    assert "price" in out


def test_spinner_runs_wrapped_code():
    calls = []
    with ux.spinner("working..."):
        calls.append(1)
    assert calls == [1]


def test_select_returns_default_when_non_interactive():
    assert ux.select("pick", ["a", "b"], default="a", non_interactive=True) == "a"


def test_select_non_interactive_without_default_raises():
    with pytest.raises(ux.NonInteractiveError):
        ux.select("pick", ["a", "b"], non_interactive=True)


def test_select_without_tty_raises_non_interactive_error(monkeypatch):
    _force_tty(monkeypatch, False)
    with pytest.raises(ux.NonInteractiveError):
        ux.select("pick", ["a", "b"])


def test_select_calls_questionary_when_interactive(monkeypatch):
    _force_tty(monkeypatch, True)
    monkeypatch.setattr(ux.questionary, "select", lambda *a, **k: _FakeQuestion("b"))
    assert ux.select("pick", ["a", "b"]) == "b"


def test_select_ctrl_c_raises_prompt_cancelled(monkeypatch):
    _force_tty(monkeypatch, True)
    monkeypatch.setattr(
        ux.questionary, "select", lambda *a, **k: _FakeQuestion(raise_exc=KeyboardInterrupt())
    )
    with pytest.raises(ux.PromptCancelled):
        ux.select("pick", ["a", "b"])


def test_checkbox_returns_default_when_non_interactive():
    assert ux.checkbox("pick many", ["a", "b"], default=[], non_interactive=True) == []
    assert ux.checkbox("pick many", ["a", "b"], default=["a"], non_interactive=True) == ["a"]


def test_checkbox_non_interactive_without_default_raises():
    with pytest.raises(ux.NonInteractiveError):
        ux.checkbox("pick many", ["a", "b"], non_interactive=True)


def test_checkbox_without_tty_raises(monkeypatch):
    _force_tty(monkeypatch, False)
    with pytest.raises(ux.NonInteractiveError):
        ux.checkbox("pick many", ["a", "b"])


def test_checkbox_calls_questionary_when_interactive(monkeypatch):
    _force_tty(monkeypatch, True)
    monkeypatch.setattr(ux.questionary, "checkbox", lambda *a, **k: _FakeQuestion(["a", "b"]))
    assert ux.checkbox("pick many", [("a", "desc"), ("b", "desc")]) == ["a", "b"]


def test_ask_text_returns_default_when_non_interactive():
    assert ux.ask_text("name?", default="widget", non_interactive=True) == "widget"


def test_ask_text_non_interactive_without_default_raises():
    with pytest.raises(ux.NonInteractiveError):
        ux.ask_text("name?", non_interactive=True)


def test_ask_text_without_tty_raises(monkeypatch):
    _force_tty(monkeypatch, False)
    with pytest.raises(ux.NonInteractiveError):
        ux.ask_text("name?")


def test_ask_text_calls_questionary_when_interactive(monkeypatch):
    _force_tty(monkeypatch, True)
    monkeypatch.setattr(ux.questionary, "text", lambda *a, **k: _FakeQuestion("widget"))
    assert ux.ask_text("name?") == "widget"


def test_confirm_returns_default_when_non_interactive():
    assert ux.confirm("sure?", default=True, non_interactive=True) is True
    assert ux.confirm("sure?", non_interactive=True) is False


def test_confirm_without_tty_raises(monkeypatch):
    _force_tty(monkeypatch, False)
    with pytest.raises(ux.NonInteractiveError):
        ux.confirm("sure?")


def test_confirm_calls_questionary_when_interactive(monkeypatch):
    _force_tty(monkeypatch, True)
    monkeypatch.setattr(ux.questionary, "confirm", lambda *a, **k: _FakeQuestion(True))
    assert ux.confirm("sure?") is True


def test_confirm_ctrl_c_raises_prompt_cancelled(monkeypatch):
    _force_tty(monkeypatch, True)
    monkeypatch.setattr(
        ux.questionary, "confirm", lambda *a, **k: _FakeQuestion(raise_exc=KeyboardInterrupt())
    )
    with pytest.raises(ux.PromptCancelled):
        ux.confirm("sure?")


def test_interactive_fields_non_interactive_returns_empty():
    assert ux.interactive_fields(non_interactive=True) == []


def test_interactive_fields_without_tty_raises(monkeypatch):
    _force_tty(monkeypatch, False)
    with pytest.raises(ux.NonInteractiveError):
        ux.interactive_fields()


def test_interactive_fields_builds_expected_strings(monkeypatch):
    _force_tty(monkeypatch, True)
    names = iter(["title", "price", ""])
    types = iter(["string", "float"])
    nullables = iter([False, True])

    monkeypatch.setattr(ux, "ask_text", lambda *a, **k: next(names))
    monkeypatch.setattr(ux, "select", lambda *a, **k: next(types))
    monkeypatch.setattr(ux, "confirm", lambda *a, **k: next(nullables))

    result = ux.interactive_fields()
    assert result == ["title:string", "price:float?"]
    assert parse_fields(result)[0].name == "title"
    assert parse_fields(result)[1].nullable is True


def test_interactive_fields_builds_references_with_target(monkeypatch):
    _force_tty(monkeypatch, True)
    names = iter(["author", ""])
    types = iter(["references"])
    targets = iter(["Person"])
    nullables = iter([False])

    def fake_ask_text(message, **kwargs):
        if "Target model" in message:
            return next(targets)
        return next(names)

    monkeypatch.setattr(ux, "ask_text", fake_ask_text)
    monkeypatch.setattr(ux, "select", lambda *a, **k: next(types))
    monkeypatch.setattr(ux, "confirm", lambda *a, **k: next(nullables))

    result = ux.interactive_fields()
    assert result == ["author:references:Person"]
    field = parse_fields(result)[0]
    assert field.kind == "references"
    assert field.target == "Person"


def test_interactive_fields_references_without_target_infers_from_name(monkeypatch):
    _force_tty(monkeypatch, True)
    names = iter(["author", ""])
    types = iter(["references"])
    targets = iter([""])
    nullables = iter([False])

    def fake_ask_text(message, **kwargs):
        if "Target model" in message:
            return next(targets)
        return next(names)

    monkeypatch.setattr(ux, "ask_text", fake_ask_text)
    monkeypatch.setattr(ux, "select", lambda *a, **k: next(types))
    monkeypatch.setattr(ux, "confirm", lambda *a, **k: next(nullables))

    result = ux.interactive_fields()
    assert result == ["author:references"]
    field = parse_fields(result)[0]
    assert field.kind == "references"
    assert field.target == "Author"


def test_print_completion_instructions_known_shells(capsys):
    for shell in ("bash", "zsh", "powershell"):
        ux.print_completion_instructions(shell)
    out = capsys.readouterr().out
    assert "register-python-argcomplete" in out


def test_print_completion_instructions_unknown_shell_raises():
    with pytest.raises(ValueError):
        ux.print_completion_instructions("fish")


def test_enable_completion_is_a_safe_noop_without_completion_env(monkeypatch):
    import argparse

    monkeypatch.delenv("_ARGCOMPLETE", raising=False)
    parser = argparse.ArgumentParser()
    ux.enable_completion(parser)
