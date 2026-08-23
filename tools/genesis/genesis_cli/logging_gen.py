import ast
from pathlib import Path

from genesis_cli.generate import GenerateError, _target_root

LOGGER_LINE = "logger = logging.getLogger(__name__)"


def _has_logger_assignment(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        func = node.value.func
        if isinstance(func, ast.Attribute) and func.attr == "getLogger":
            return True
    return False


def _has_logging_import(tree: ast.Module) -> bool:
    return any(
        isinstance(node, ast.Import) and any(alias.name == "logging" for alias in node.names)
        for node in tree.body
    )


def _leading_plain_imports(tree: ast.Module) -> list[ast.Import]:
    leading = []
    for node in tree.body:
        if not isinstance(node, ast.Import):
            break
        leading.append(node)
    return leading


def _insert_logging_import(source: str, tree: ast.Module) -> str:
    lines = source.splitlines()
    leading = _leading_plain_imports(tree)

    if leading:
        insert_at = 0
        for node in leading:
            if node.names[0].name > "logging":
                break
            insert_at = node.end_lineno
        lines.insert(insert_at, "import logging")
        return "\n".join(lines) + "\n"

    imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    insert_at = imports[0].lineno - 1 if imports else 0
    lines[insert_at:insert_at] = ["import logging", ""]
    return "\n".join(lines) + "\n"


def _insert_logger_line(source: str) -> str:
    tree = ast.parse(source)
    imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    lines = source.splitlines()
    last_import_end = imports[-1].end_lineno if imports else 0

    rest = lines[last_import_end:]
    while rest and rest[0] == "":
        rest.pop(0)
    starts_block = bool(rest) and rest[0].startswith(("@", "def ", "class "))
    gap = ["", ""] if starts_block else [""]

    new_lines = lines[:last_import_end] + [""] + [LOGGER_LINE] + gap + rest
    return "\n".join(new_lines) + "\n"


def add_logger(target: Path, file: str) -> tuple[Path, bool]:
    target = _target_root(target)
    path = Path(file)
    if not path.is_absolute():
        path = target / file
    if not path.exists():
        raise GenerateError(f"{path} does not exist")

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    if _has_logger_assignment(tree):
        return path, False

    if not _has_logging_import(tree):
        source = _insert_logging_import(source, tree)

    path.write_text(_insert_logger_line(source), encoding="utf-8")
    return path, True
