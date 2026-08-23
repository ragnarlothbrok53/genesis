import ast
import re
from pathlib import Path

from genesis_cli.modules import load_kernel, load_modules

ROUTE_EXPORT = re.compile(r'export\s+const\s+route\s*=\s*["\']([^"\']+)["\']')
NAV_EXPORT = re.compile(r"export\s+const\s+nav\s*=\s*\{([^}]*)\}")
NAV_LABEL = re.compile(r'label:\s*["\']([^"\']+)["\']')
NAV_ORDER = re.compile(r"order:\s*(\d+)")

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return None


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _literal(node: ast.AST):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return None


def _annotation(node: ast.AST | None) -> str:
    if node is None:
        return ""
    return ast.unparse(node)


def _peewee_fields(body: list[ast.stmt]) -> list[dict]:
    fields = []
    for statement in body:
        if not isinstance(statement, ast.Assign) or not isinstance(statement.value, ast.Call):
            continue
        kind = _call_name(statement.value.func)
        if kind is None:
            continue
        for target in statement.targets:
            if isinstance(target, ast.Name):
                nullable = any(
                    keyword.arg == "null" and _literal(keyword.value) is True
                    for keyword in statement.value.keywords
                )
                fields.append({"name": target.id, "type": kind, "null": nullable})
    return fields


def _table_name(body: list[ast.stmt], default: str) -> str:
    for statement in body:
        if isinstance(statement, ast.ClassDef) and statement.name == "Meta":
            for inner in statement.body:
                if isinstance(inner, ast.Assign):
                    for target in inner.targets:
                        if isinstance(target, ast.Name) and target.id == "table_name":
                            return _literal(inner.value) or default
    return default


def _shape_fields(body: list[ast.stmt]) -> list[dict]:
    fields = []
    for statement in body:
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            fields.append(
                {"name": statement.target.id, "type": _annotation(statement.annotation)}
            )
    return fields


def scan_models(root: Path) -> tuple[list[dict], list[dict]]:
    tables, shapes = [], []
    for path in sorted((root / "backend" / "app" / "models").glob("*.py")):
        if path.name.startswith("_"):
            continue
        tree = _parse(path)
        if tree is None:
            continue
        relative = f"backend/app/models/{path.name}"
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            bases = [ast.unparse(base) for base in node.bases]
            if "db.Model" in bases:
                tables.append(
                    {
                        "model": node.name,
                        "table": _table_name(node.body, node.name.lower()),
                        "file": relative,
                        "columns": _peewee_fields(node.body),
                    }
                )
            elif "BaseModel" in bases:
                shapes.append(
                    {"shape": node.name, "file": relative, "fields": _shape_fields(node.body)}
                )
    return tables, shapes


def scan_endpoints(root: Path) -> list[dict]:
    endpoints = []
    for path in sorted((root / "backend" / "app" / "endpoints").glob("*.py")):
        if path.name.startswith("_"):
            continue
        tree = _parse(path)
        if tree is None:
            continue

        prefix = ""
        for node in tree.body:
            if (
                isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Call)
                and _call_name(node.value.func) == "router"
                and node.value.args
            ):
                prefix = _literal(node.value.args[0]) or ""

        routes = []
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                method = _call_name(decorator.func)
                if method not in HTTP_METHODS:
                    continue
                keywords = {
                    keyword.arg: keyword.value
                    for keyword in decorator.keywords
                    if keyword.arg
                }
                routes.append(
                    {
                        "method": method.upper(),
                        "path": (_literal(decorator.args[0]) if decorator.args else "") or "",
                        "handler": node.name,
                        "response_model": _annotation(keywords.get("response_model")),
                        "status_code": _literal(keywords["status_code"])
                        if "status_code" in keywords
                        else None,
                    }
                )

        if routes:
            endpoints.append(
                {
                    "prefix": prefix,
                    "file": f"backend/app/endpoints/{path.name}",
                    "routes": sorted(routes, key=lambda route: (route["path"], route["method"])),
                }
            )
    return endpoints


def scan_tasks(root: Path) -> list[dict]:
    tasks = []
    directory = root / "backend" / "app" / "tasks"
    if not directory.is_dir():
        return tasks
    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("_"):
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if any(_call_name(decorator) == "task" for decorator in node.decorator_list):
                tasks.append({"task": node.name, "file": f"backend/app/tasks/{path.name}"})
    return tasks


def scan_pages(root: Path) -> list[dict]:
    pages = []
    for path in sorted((root / "frontend" / "src" / "pages").glob("*.tsx")):
        text = path.read_text(encoding="utf-8")
        route = ROUTE_EXPORT.search(text)
        if not route:
            continue
        nav = NAV_EXPORT.search(text)
        label = NAV_LABEL.search(nav.group(1)).group(1) if nav and NAV_LABEL.search(nav.group(1)) else None
        order = int(NAV_ORDER.search(nav.group(1)).group(1)) if nav and NAV_ORDER.search(nav.group(1)) else None
        pages.append(
            {
                "route": route.group(1),
                "nav": label,
                "order": order,
                "file": f"frontend/src/pages/{path.name}",
            }
        )
    return sorted(pages, key=lambda page: (page["order"] is None, page["order"], page["route"]))


def installed_modules(root: Path, modules: dict[str, dict]) -> list[str]:
    present = []
    for name, manifest in modules.items():
        owned = manifest.get("files", [])
        if owned and any((root / entry.rstrip("/")).exists() for entry in owned):
            present.append(name)
    return sorted(present)


def scan(root: Path) -> dict:
    modules = load_modules(root / "modules")
    kernel = load_kernel(root / "modules")
    present = installed_modules(root, modules)

    services = list(kernel.get("service", []))
    for name in present:
        services += modules[name].get("service", [])

    tables, shapes = scan_models(root)
    return {
        "genesis": {"template": str(root.name), "api_version": "v1"},
        "modules": {
            "installed": present,
            "available": sorted(modules),
            "summaries": {name: modules[name].get("summary", "") for name in sorted(modules)},
        },
        "services": [
            {
                "name": service["name"],
                "capability": service.get("capability"),
                "port": service.get("port"),
                "image": service.get("image"),
            }
            for service in services
        ],
        "tables": tables,
        "shapes": shapes,
        "endpoints": scan_endpoints(root),
        "tasks": scan_tasks(root),
        "pages": scan_pages(root),
    }
