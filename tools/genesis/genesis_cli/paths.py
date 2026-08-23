from pathlib import Path

SKIP_DIRS = {
    ".git",
    ".venv",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "dist",
    "tools",
    ".claude",
    ".beads",
    ".agents",
    ".codex",
}

SKIP_FILES = {".env", "settings.local.json", "*.pyc"}

TEXT_SUFFIXES = {
    ".py",
    ".toml",
    ".conf",
    ".yml",
    ".yaml",
    ".ts",
    ".tsx",
    ".json",
    ".md",
    ".sh",
    ".txt",
    ".cmd",
    ".ps1",
    ".example",
}


def is_text(path: Path) -> bool:
    return path.suffix in TEXT_SUFFIXES or path.name == "Dockerfile"


def iter_text_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file() or not is_text(path):
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path
