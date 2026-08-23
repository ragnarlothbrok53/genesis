"""Interactive/color UX toolkit for the genesis CLI.

Nothing in this file is wired into cli.py yet — it is a standalone toolkit
for another pass to apply. Wiring notes for that pass:

Styled output (never raises, safe in CI):
    success(msg: str) -> None        green "check mark" line
    error(msg: str) -> None          red "x" line, printed to stderr
    warning(msg: str) -> None        yellow "!" line
    info(msg: str) -> None           blue "i" line
    table(headers: list[str], rows: list[list[str]]) -> None
        Drop-in replacement for the manual f"{x:<12}" printing in
        show_map/list_presets/list_modules — call once per section with
        that section's headers and rows instead of a loop of print().
    spinner(message: str) -> context manager
        Wrap a long call, e.g.:
            with spinner("building image..."):
                subprocess.run(...)
        Purely cosmetic — does not capture or change the wrapped call's
        return value or exceptions.

Interactive prompts (each takes non_interactive: bool = False):
    select(message, choices, *, default=None, non_interactive=False) -> str
    checkbox(message, choices, *, default=None, non_interactive=False) -> list[str]
    ask_text(message, *, validate=None, default=None, non_interactive=False) -> str
    confirm(message, *, default=False, non_interactive=False) -> bool

    `choices` accepts a list of plain strings, or (value, description)
    tuples to render a description next to each option.

    Non-interactive/CI behavior (this is the part to get right when wiring):
    - If the caller passes non_interactive=True, the function never touches
      the terminal — it returns `default` immediately, or raises
      NonInteractiveError if no usable default was given. A cli.py handler
      should pass non_interactive=True whenever the equivalent value was
      already supplied as a flag/positional arg, so scripted/CI usage that
      always passes explicit args never prompts.
    - If non_interactive=False (the default) and stdin/stdout are not a
      real terminal (e.g. under pytest, in CI, or piped), the function
      raises NonInteractiveError itself rather than hanging on a prompt
      that can never be answered. A cli.py handler should catch this
      alongside its other *Error types and print a message telling the
      user which flag to pass instead.
    - Ctrl+C during an actual prompt raises PromptCancelled, not a raw
      KeyboardInterrupt traceback — catch it in cli.py's top-level
      try/except next to ModuleError etc. and exit(1) quietly.

Field builder (for generate model/page/scaffold/task's field:type args):
    interactive_fields(*, non_interactive=False) -> list[str]
        Loops: field name (blank = done) -> type picker -> nullable? ->
        (target model, only for "references") -> repeat. Returns strings
        in the exact "name:type" / "name:type?" / "name:references:Target?"
        format genesis_cli.fields.parse_fields already accepts. A cli.py
        handler should call this when the user ran e.g.
        `genesis generate model Item` with no trailing fields and stdin is
        a terminal, then pass the result straight to parse_fields(). With
        non_interactive=True it returns [] immediately without prompting.

Shell completion:
    enable_completion(parser: argparse.ArgumentParser) -> None
        Call once, right before parser.parse_args() in main(). No-op
        unless the shell's completion hook is actually invoking the
        process, so it's always safe to call.
    print_completion_instructions(shell: str) -> None
        shell is one of "bash", "zsh", "powershell". Prints the exact
        line the user should add to their shell profile.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import argcomplete
import questionary
from rich.console import Console
from rich.table import Table

from genesis_cli.fields import TYPES

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

console = Console()
_err_console = Console(stderr=True)

_STYLE = questionary.Style(
    [
        ("qmark", "fg:#00d7af bold"),
        ("question", "bold"),
        ("pointer", "fg:#00d7af bold"),
        ("highlighted", "fg:#00d7af bold"),
        ("selected", "fg:#00d7af"),
        ("answer", "fg:#00d7af bold"),
    ]
)

_FIELD_TYPES = ["string", "text", "int", "float", "bool", "datetime"]
_FIELD_TYPE_DESCRIPTIONS = {
    "string": "short text, max 200 chars",
    "text": "long text",
    "int": "integer",
    "float": "decimal number",
    "bool": "true/false",
    "datetime": "date and time",
    "references": "foreign key to another model",
}
assert set(_FIELD_TYPES) <= set(TYPES)

_COMPLETION_INSTRUCTIONS = {
    "bash": 'eval "$(register-python-argcomplete genesis)"',
    "zsh": 'eval "$(register-python-argcomplete genesis)"',
    "powershell": "register-python-argcomplete --shell powershell genesis | Out-String | Invoke-Expression",
}


class PromptCancelled(Exception):
    pass


class NonInteractiveError(Exception):
    pass


def success(msg: str) -> None:
    console.print(f"[green]✓[/green] {msg}")


def error(msg: str) -> None:
    _err_console.print(f"[red]✗[/red] {msg}")


def warning(msg: str) -> None:
    console.print(f"[yellow]![/yellow] {msg}")


def info(msg: str) -> None:
    console.print(f"[blue]i[/blue] {msg}")


def table(headers: list[str], rows: list[list[str]]) -> None:
    grid = Table()
    for header in headers:
        grid.add_column(header)
    for row in rows:
        grid.add_row(*[str(cell) for cell in row])
    console.print(grid)


@contextmanager
def spinner(message: str) -> Iterator[None]:
    with console.status(message, spinner="dots"):
        yield


def _is_tty() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _resolve(non_interactive: bool, default, what: str):
    if non_interactive:
        if default is None:
            raise NonInteractiveError(
                f"{what} needs a value but non_interactive=True was passed with no default"
            )
        return True, default
    if not _is_tty():
        raise NonInteractiveError(
            f"cannot prompt for {what} — no terminal attached; "
            "pass the value directly or call with non_interactive=True and a default"
        )
    return False, default


def _run(question) -> object:
    try:
        return question.unsafe_ask()
    except (KeyboardInterrupt, EOFError) as exc:
        raise PromptCancelled(str(exc)) from exc


def _as_choice(entry) -> questionary.Choice:
    if isinstance(entry, tuple):
        value, description = entry
        title = f"{value} — {description}" if description else str(value)
        return questionary.Choice(title=title, value=value)
    return questionary.Choice(title=str(entry), value=entry)


def select(
    message: str,
    choices: list,
    *,
    default: str | None = None,
    non_interactive: bool = False,
) -> str:
    use_default, value = _resolve(non_interactive, default, f"select '{message}'")
    if use_default:
        return value
    return _run(
        questionary.select(
            message, choices=[_as_choice(c) for c in choices], default=default, style=_STYLE
        )
    )


def checkbox(
    message: str,
    choices: list,
    *,
    default: list[str] | None = None,
    non_interactive: bool = False,
) -> list[str]:
    use_default, value = _resolve(non_interactive, default, f"checkbox '{message}'")
    if use_default:
        return value
    options = []
    for entry in choices:
        picked = _as_choice(entry)
        picked.checked = picked.value in (default or [])
        options.append(picked)
    return _run(questionary.checkbox(message, choices=options, style=_STYLE))


def ask_text(
    message: str,
    *,
    validate: Callable[[str], bool] | None = None,
    default: str | None = None,
    non_interactive: bool = False,
) -> str:
    use_default, value = _resolve(non_interactive, default, f"text '{message}'")
    if use_default:
        return value

    def _validator(text: str) -> bool:
        return True if validate is None else bool(validate(text))

    return _run(questionary.text(message, default=default or "", validate=_validator, style=_STYLE))


def confirm(message: str, *, default: bool = False, non_interactive: bool = False) -> bool:
    if non_interactive:
        return default
    if not _is_tty():
        raise NonInteractiveError(
            f"cannot prompt to confirm '{message}' — no terminal attached; "
            "pass non_interactive=True with an explicit default"
        )
    return _run(questionary.confirm(message, default=default, style=_STYLE))


def interactive_fields(*, non_interactive: bool = False) -> list[str]:
    if non_interactive:
        return []
    if not _is_tty():
        raise NonInteractiveError(
            "interactive field builder needs a terminal — pass fields as name:type arguments instead"
        )

    type_choices = [(name, _FIELD_TYPE_DESCRIPTIONS[name]) for name in [*_FIELD_TYPES, "references"]]

    fields: list[str] = []
    while True:
        name = ask_text(f"Field {len(fields) + 1} name (blank to finish):", default="")
        if not name:
            return fields

        kind = select("Field type:", type_choices)
        target = ""
        if kind == "references":
            target = ask_text(
                "Target model (blank to infer from field name):", default=""
            )
        nullable = confirm("Nullable?", default=False)

        suffix = "?" if nullable else ""
        if kind == "references" and target:
            fields.append(f"{name}:references:{target}{suffix}")
        else:
            fields.append(f"{name}:{kind}{suffix}")


def enable_completion(parser: argparse.ArgumentParser) -> None:
    argcomplete.autocomplete(parser)


def print_completion_instructions(shell: str) -> None:
    if shell not in _COMPLETION_INSTRUCTIONS:
        raise ValueError(f"unsupported shell '{shell}' — choose from {', '.join(_COMPLETION_INSTRUCTIONS)}")
    info("add this line to your shell profile to enable tab completion:")
    console.print(f"  {_COMPLETION_INSTRUCTIONS[shell]}")
