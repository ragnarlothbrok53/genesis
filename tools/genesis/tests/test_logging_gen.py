import ast

import pytest

from genesis_cli.generate import GenerateError, generate_model
from genesis_cli.logging_gen import add_logger
from tests.test_generate import make_project


def _write(project, relative, content):
    path = project / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_add_logger_to_file_with_no_imports(tmp_path):
    project = make_project(tmp_path, "l1")
    path = _write(
        project,
        "backend/app/tasks/reports.py",
        'from genesis import task\n\n\n@task\ndef summarize_items(count: int) -> str:\n'
        '    return f"processed {count} items"\n',
    )

    generated_path, changed = add_logger(project, "backend/app/tasks/reports.py")

    assert changed
    assert generated_path == path
    source = path.read_text(encoding="utf-8")
    ast.parse(source)
    assert "import logging" in source
    assert "logger = logging.getLogger(__name__)" in source
    assert source.index("import logging") < source.index("logger = logging.getLogger")
    assert source.index("logger = logging.getLogger") < source.index("@task")


def test_add_logger_is_idempotent(tmp_path):
    project = make_project(tmp_path, "l2")
    _write(
        project,
        "backend/app/tasks/reports.py",
        'from genesis import task\n\n\n@task\ndef summarize_items(count: int) -> str:\n'
        '    return f"processed {count} items"\n',
    )

    add_logger(project, "backend/app/tasks/reports.py")
    path = project / "backend/app/tasks/reports.py"
    first_pass = path.read_text(encoding="utf-8")

    _, changed_again = add_logger(project, "backend/app/tasks/reports.py")
    second_pass = path.read_text(encoding="utf-8")

    assert not changed_again
    assert first_pass == second_pass
    assert first_pass.count("import logging") == 1
    assert first_pass.count("logger = logging.getLogger(__name__)") == 1


def test_add_logger_does_not_duplicate_existing_logging_import(tmp_path):
    project = make_project(tmp_path, "l3")
    path = _write(
        project,
        "backend/app/tasks/reports.py",
        "import logging\n\nfrom genesis import task\n\n\n@task\ndef noisy() -> None:\n"
        '    logging.info("still runs")\n',
    )

    _, changed = add_logger(project, "backend/app/tasks/reports.py")

    assert changed
    source = path.read_text(encoding="utf-8")
    ast.parse(source)
    assert source.count("import logging") == 1
    assert "logger = logging.getLogger(__name__)" in source


def test_add_logger_missing_file_raises(tmp_path):
    project = make_project(tmp_path, "l4")
    with pytest.raises(GenerateError, match="does not exist"):
        add_logger(project, "backend/app/tasks/missing.py")


def test_add_logger_on_generated_model_stays_valid_python(tmp_path):
    project = make_project(tmp_path, "l5")
    path = generate_model(project, "Product", [])

    add_logger(project, str(path.relative_to(project)))

    source = path.read_text(encoding="utf-8")
    ast.parse(source)
    assert "logger = logging.getLogger(__name__)" in source
