import argparse
import functools
import shutil
import subprocess
import sys
from pathlib import Path

from genesis_cli import ux
from genesis_cli.compose import render_compose
from genesis_cli.deploy import DeployError
from genesis_cli.deploy import deploy as deploy_fly
from genesis_cli.docs import render_all
from genesis_cli.doctor import install_uv, run_checks
from genesis_cli.fields import FieldError, parse_fields
from genesis_cli.generate import (
    GenerateError,
    destroy_admin,
    destroy_endpoint,
    destroy_model,
    destroy_page,
    destroy_scaffold,
    destroy_task,
    generate_admin,
    generate_endpoint,
    generate_model,
    generate_page,
    generate_scaffold,
    generate_task,
    promote_task,
)
from genesis_cli.inflect import pascal_case, pluralize, snake_case
from genesis_cli.local import LocalError, dev_local
from genesis_cli.logging_gen import add_logger
from genesis_cli.modules import ModuleError, load_kernel, load_modules, resolve
from genesis_cli.ops import OpsError, build, dev, down, logs, migrate, restart
from genesis_cli.paths import SKIP_DIRS, SKIP_FILES, is_text
from genesis_cli.presets import excluded_for, load_presets, write_env
from genesis_cli.scan import installed_modules, scan
from genesis_cli.strip import MarkerError, declared_markers, strip_excluded
from genesis_cli.sync import SyncError, _npm_relock, _remove_npm_deps
from genesis_cli.sync import add as sync_add
from genesis_cli.sync import remove as sync_remove


def _is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _search_roots() -> list[Path]:
    cwd = Path.cwd().resolve()
    package_dir = Path(__file__).resolve().parent
    return [cwd, *cwd.parents, package_dir, *package_dir.parents]


def find_template(explicit: str | None = None) -> Path:
    if explicit:
        candidate = Path(explicit).resolve()
        if not (candidate / "modules" / "kernel.toml").is_file():
            raise ModuleError(f"{candidate} is not a genesis template (no modules/kernel.toml)")
        return candidate

    for directory in _search_roots():
        if (directory / "modules" / "kernel.toml").is_file():
            return directory

    raise ModuleError(
        "no genesis template found — run this inside a genesis repository, or pass --source PATH"
    )


def _delete_owned_files(root: Path, modules: dict[str, dict], excluded: set[str]) -> list[str]:
    removed = []
    for name in sorted(excluded):
        for entry in modules[name].get("files", []):
            target = root / entry.rstrip("/")
            if not target.exists():
                continue
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            removed.append(entry)
    return removed


def _strip_tree(root: Path, known: set[str], excluded: set[str]) -> list[str]:
    changed = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or not is_text(path):
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        original = path.read_text(encoding="utf-8")
        if not any(kind in original for kind in ("module:", "service:", "topology:")):
            continue

        unknown = declared_markers(original) - known
        if unknown:
            raise MarkerError(f"{path}: unknown marker(s): {', '.join(sorted(unknown))}")

        stripped = strip_excluded(original, excluded, source=str(path))
        if stripped != original:
            path.write_text(stripped, encoding="utf-8")
            changed.append(str(path.relative_to(root)).replace("\\", "/"))
    return changed


def _rewrite_nginx_upstreams(root: Path, services: list[dict]) -> None:
    nginx = root / "deploy" / "nginx.conf"
    if not nginx.exists():
        return
    text = nginx.read_text(encoding="utf-8")
    hosts = {service["port"]: service["name"] for service in services if service.get("port")}
    hosts[8000] = "app"
    for port, host in hosts.items():
        text = text.replace(f"127.0.0.1:{port}", f"{host}:{port}")
    nginx.write_text(text, encoding="utf-8")


def _relock(root: Path) -> bool:
    backend = root / "backend"
    lock = backend / "uv.lock"
    if lock.exists():
        lock.unlink()
    try:
        subprocess.run(["uv", "lock", "--directory", str(backend)], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def render(args: argparse.Namespace) -> int:
    root = find_template(args.source)
    modules = load_modules(root / "modules")
    kernel = load_kernel(root / "modules")
    excluded_modules = set(args.without)
    selected = resolve(modules, excluded_modules)

    services = list(kernel.get("service", []))
    processes = list(kernel.get("process", []))
    for name in sorted(selected):
        services += modules[name].get("service", [])
        processes += modules[name].get("process", [])
    if args.topology != "compose":
        services = [service for service in services if not service.get("compose_only")]

    known = (
        {f"module:{name}" for name in modules}
        | {"topology:single", "topology:compose"}
        | {f"service:{service['name']}" for service in kernel.get("service", [])}
        | {
            f"service:{service['name']}"
            for manifest in modules.values()
            for service in manifest.get("service", [])
        }
    )

    excluded = {f"module:{name}" for name in excluded_modules}
    if args.topology == "compose":
        excluded |= {f"service:{service['name']}" for service in services}
        excluded.add("topology:single")
    else:
        excluded.add("topology:compose")

    destination = Path(args.out).resolve()
    if destination.exists():
        if not args.force:
            ux.error(f"{destination} already exists (use --force)")
            return 1
        shutil.rmtree(destination)

    shutil.copytree(root, destination, ignore=shutil.ignore_patterns(*SKIP_DIRS, *SKIP_FILES))
    removed = _delete_owned_files(destination, modules, excluded_modules)
    changed = _strip_tree(destination, known, excluded)

    if args.topology == "compose":
        project = destination.name.strip("_") or "app"
        compose = render_compose(project, services, processes)
        (destination / "docker-compose.yml").write_text(compose, encoding="utf-8")
        _rewrite_nginx_upstreams(destination, services)
        for name in ("supervisord.conf", "entrypoint.sh", "fatal_listener.py"):
            (destination / "deploy" / name).unlink(missing_ok=True)

    relocked = _relock(destination)

    npm_deps_to_remove = [
        dep for name in excluded_modules for dep in modules.get(name, {}).get("npm_deps", [])
    ]
    npm_removed = _remove_npm_deps(destination, npm_deps_to_remove)
    _npm_relock(destination, npm_removed)

    ux.success(f"rendered {destination}")
    ux.info(f"topology: {args.topology}")
    ux.info(f"modules:  {', '.join(sorted(selected)) or 'none'}")
    ux.info(f"excluded: {', '.join(sorted(excluded_modules)) or 'none'}")
    ux.info(f"services: {', '.join(service['name'] for service in services)}")
    ux.info(f"deleted:  {len(removed)} path(s)")
    ux.info(f"stripped: {len(changed)} file(s)")
    if not relocked:
        ux.warning("could not regenerate backend/uv.lock — run 'uv lock' in backend/")
    return 0


def create(args: argparse.Namespace) -> int:
    root = find_template(args.source)
    presets = load_presets(root / "modules")
    available = set(load_modules(root / "modules"))

    interactive = _is_interactive()
    preset_given = args.preset is not None
    preset = args.preset
    if preset is None:
        choices = [(name, presets[name].get("summary", "")) for name in sorted(presets)]
        preset = ux.select(
            "Choose a preset:", choices, default="full", non_interactive=not interactive
        )

    without = list(args.without)
    if not without and not preset_given and interactive:
        included_by_preset = sorted(available - excluded_for(presets, available, preset))
        included = ux.checkbox(
            "Modules to include: (space to toggle, enter to continue)",
            sorted(available),
            default=included_by_preset,
        )
        without = sorted(available - set(included))

    excluded = sorted(excluded_for(presets, available, preset) | set(without))
    destination = Path(args.out or args.name).resolve()

    code = render(
        argparse.Namespace(
            out=str(destination),
            without=excluded,
            topology=args.topology,
            force=args.force,
            source=args.source,
        )
    )
    if code != 0:
        return code

    env = write_env(destination, args.name)
    rendered = render_all(scan(destination))
    for name, content in rendered.items():
        (destination / name).write_text(content, encoding="utf-8")

    ux.info(f"preset:   {preset}")
    ux.info(f"env:      {env.name} written with generated secrets")
    ux.info(f"docs:     {len(rendered)} generated")
    print()
    print("next:")
    print(f"  cd {destination.name}")
    print("  genesis dev")
    return 0


def _project_target(args: argparse.Namespace) -> Path:
    return Path.cwd().resolve() if not args.target else Path(args.target).resolve()


def _regen_docs(target: Path) -> int:
    rendered = render_all(scan(target))
    for name, content in rendered.items():
        (target / name).write_text(content, encoding="utf-8")
    return len(rendered)


def _fields_or_prompt(fields: list[str]) -> list[str]:
    if fields:
        return fields
    if not _is_interactive():
        return []
    return ux.interactive_fields()


def generate_model_cmd(args: argparse.Namespace) -> int:
    target = _project_target(args)
    fields = parse_fields(_fields_or_prompt(args.fields))
    path = generate_model(target, args.name, fields, force=args.force)
    ux.success(f"wrote {path.relative_to(target)}")
    ux.info(f"docs: {_regen_docs(target)} regenerated")
    print()
    print(f'next: genesis migrate "add {path.stem}s"  (once the app is running)')
    return 0


def generate_endpoint_cmd(args: argparse.Namespace) -> int:
    target = _project_target(args)
    path = generate_endpoint(target, args.name, force=args.force)
    ux.success(f"wrote {path.relative_to(target)}")
    ux.info(f"docs: {_regen_docs(target)} regenerated")
    print()
    print("next: genesis restart  (reload the running app to pick it up)")
    return 0


def generate_page_cmd(args: argparse.Namespace) -> int:
    target = _project_target(args)
    fields = parse_fields(_fields_or_prompt(args.fields))
    path = generate_page(target, args.name, fields, force=args.force)
    ux.success(f"wrote {path.relative_to(target)}")
    print()
    print("next: cd frontend && npm run types  (pick up the new API shapes)")
    return 0


def generate_admin_cmd(args: argparse.Namespace) -> int:
    target = _project_target(args)
    path, editable = generate_admin(target, args.name, force=args.force)
    ux.success(f"wrote {path.relative_to(target)}")
    if not editable:
        ux.warning(
            f"the /api/v1/{pluralize(snake_case(args.name))} endpoint has no PATCH/PUT route "
            "— generated a delete-only admin page; run 'genesis generate endpoint "
            f"{args.name} --force' to add update support first if you want inline edit"
        )
    print()
    print("next: cd frontend && npm run types  (pick up the new API shapes)")
    return 0


def generate_logger_cmd(args: argparse.Namespace) -> int:
    target = _project_target(args)
    path, changed = add_logger(target, args.file)
    try:
        display = path.relative_to(target)
    except ValueError:
        display = path
    if not changed:
        ux.info(f"{display} already has a logger")
        return 0
    ux.success(f"added logger boilerplate to {display}")
    return 0


def generate_task_cmd(args: argparse.Namespace) -> int:
    target = _project_target(args)
    if args.source:
        path, warnings = promote_task(target, args.source, force=args.force)
        ux.success(f"wrote {path.relative_to(target)}")
        for warning in warnings:
            ux.warning(warning)
        return 0
    if not args.name:
        raise GenerateError("a task name is required unless --source is given")
    fields = parse_fields(args.fields)
    path = generate_task(target, args.name, fields, force=args.force)
    ux.success(f"wrote {path.relative_to(target)}")
    print()
    print("next: use genesis.jobs.run_task(...) from an endpoint to call it")
    return 0


def generate_scaffold_cmd(args: argparse.Namespace) -> int:
    target = _project_target(args)
    fields = parse_fields(_fields_or_prompt(args.fields))
    paths = generate_scaffold(target, args.name, fields, force=args.force)
    for kind, path in paths.items():
        ux.success(f"{kind:<9} {path.relative_to(target)}")
    ux.info(f"docs      {_regen_docs(target)} regenerated")
    print()
    print("next:")
    print(f'  genesis migrate "add {paths["model"].stem}s"   (once the app is running)')
    print("  genesis restart                          (reload the API)")
    print("  cd frontend && npm run types              (pick up the new page types)")
    return 0


def _confirm_destroy(args: argparse.Namespace, description: str) -> bool:
    if getattr(args, "force", False):
        return True
    if not _is_interactive():
        ux.error(f"refusing to delete {description} without confirmation — pass --force")
        return False
    return ux.confirm(f"Delete {description}?", default=False)


def destroy_model_cmd(args: argparse.Namespace) -> int:
    target = _project_target(args)
    if not _confirm_destroy(args, f"backend/app/models/{snake_case(args.name)}.py"):
        return 1
    path = destroy_model(target, args.name)
    ux.success(f"removed {path.relative_to(target)}")
    ux.info(f"docs: {_regen_docs(target)} regenerated")
    return 0


def destroy_endpoint_cmd(args: argparse.Namespace) -> int:
    target = _project_target(args)
    description = f"backend/app/endpoints/{pluralize(snake_case(args.name))}.py"
    if not _confirm_destroy(args, description):
        return 1
    path = destroy_endpoint(target, args.name)
    ux.success(f"removed {path.relative_to(target)}")
    ux.info(f"docs: {_regen_docs(target)} regenerated")
    return 0


def destroy_page_cmd(args: argparse.Namespace) -> int:
    target = _project_target(args)
    description = f"frontend/src/pages/{pascal_case(pluralize(snake_case(args.name)))}.tsx"
    if not _confirm_destroy(args, description):
        return 1
    path = destroy_page(target, args.name)
    ux.success(f"removed {path.relative_to(target)}")
    return 0


def destroy_admin_cmd(args: argparse.Namespace) -> int:
    target = _project_target(args)
    description = f"frontend/src/pages/Admin{pascal_case(pluralize(snake_case(args.name)))}.tsx"
    if not _confirm_destroy(args, description):
        return 1
    path = destroy_admin(target, args.name)
    ux.success(f"removed {path.relative_to(target)}")
    return 0


def destroy_task_cmd(args: argparse.Namespace) -> int:
    target = _project_target(args)
    if not _confirm_destroy(args, f"backend/app/tasks/{snake_case(args.name)}.py"):
        return 1
    path = destroy_task(target, args.name)
    ux.success(f"removed {path.relative_to(target)}")
    return 0


def destroy_scaffold_cmd(args: argparse.Namespace) -> int:
    target = _project_target(args)
    if not _confirm_destroy(args, f"the model, endpoint and page for '{args.name}'"):
        return 1
    paths = destroy_scaffold(target, args.name)
    for kind, path in paths.items():
        ux.success(f"{kind:<9} removed {path.relative_to(target)}")
    ux.info(f"docs      {_regen_docs(target)} regenerated")
    return 0


def add_module(args: argparse.Namespace) -> int:
    target = Path.cwd().resolve() if not args.target else Path(args.target).resolve()
    source = find_template(args.source)
    modules = load_modules(source / "modules")
    installed = set(installed_modules(target, modules))

    module_names = [args.module] if args.module else ux.checkbox(
        "Select module(s) to add:",
        [(name, modules[name].get("summary", "")) for name in sorted(modules) if name not in installed],
    )
    if not module_names:
        ux.warning("no modules selected")
        return 0

    for module_name in module_names:
        result = sync_add(target, source, module_name, relock=False)
        ux.success(f"added {', '.join(result['added'])}")
        if result["copied"]:
            ux.info(f"copied:        {len(result['copied'])} path(s)")
        if result["infra_updated"]:
            ux.info(f"infra updated: {', '.join(result['infra_updated'])}")
        if result["infra_skipped"]:
            ux.warning(f"infra skipped (locally modified): {', '.join(result['infra_skipped'])}")
        if result["env_appended"]:
            keys = ", ".join(line.split("=", 1)[0] for line in result["env_appended"])
            ux.info(f".env:          appended {keys}")

    if not _relock(target):
        ux.warning("could not regenerate backend/uv.lock — run 'uv lock' in backend/")

    rendered = render_all(scan(target))
    for name, content in rendered.items():
        (target / name).write_text(content, encoding="utf-8")
    ux.info(f"docs:          {len(rendered)} regenerated")
    return 0


def remove_module(args: argparse.Namespace) -> int:
    target = Path.cwd().resolve() if not args.target else Path(args.target).resolve()
    source = find_template(args.source)
    modules = load_modules(source / "modules")
    installed = set(installed_modules(target, modules))

    module_names = [args.module] if args.module else ux.checkbox(
        "Select module(s) to remove:",
        [(name, modules[name].get("summary", "")) for name in sorted(installed)],
    )
    if not module_names:
        ux.warning("no modules selected")
        return 0

    for module_name in module_names:
        result = sync_remove(target, source, module_name, relock=False)
        ux.success(f"removed {module_name}")
        ux.info(f"deleted:       {len(result['removed_files'])} path(s)")
        if result["infra_updated"]:
            ux.info(f"infra updated: {', '.join(result['infra_updated'])}")
        if result["infra_skipped"]:
            ux.warning(f"infra skipped (locally modified): {', '.join(result['infra_skipped'])}")

    if not _relock(target):
        ux.warning("could not regenerate backend/uv.lock — run 'uv lock' in backend/")

    rendered = render_all(scan(target))
    for name, content in rendered.items():
        (target / name).write_text(content, encoding="utf-8")
    ux.info(f"docs:          {len(rendered)} regenerated")
    return 0


def show_map(args: argparse.Namespace) -> int:
    graph = scan(find_template(args.source))

    ux.info(f"modules: {', '.join(graph['modules']['installed']) or 'none'}")

    print("\nendpoints")
    endpoint_rows = [
        [route["method"], f"/api/v1{endpoint['prefix']}{route['path']}", endpoint["file"]]
        for endpoint in graph["endpoints"]
        for route in endpoint["routes"]
    ]
    ux.table(["method", "path", "file"], endpoint_rows)

    print("\ntables")
    ux.table(
        ["table", "model", "columns"],
        [
            [
                table["table"],
                table["model"],
                ", ".join(column["name"] for column in table["columns"]),
            ]
            for table in graph["tables"]
        ],
    )

    print("\ntasks")
    if graph["tasks"]:
        ux.table(["task", "file"], [[task["task"], task["file"]] for task in graph["tasks"]])
    else:
        print("  none")

    print("\npages")
    ux.table(
        ["route", "nav", "file"],
        [[page["route"], page["nav"] or "-", page["file"]] for page in graph["pages"]],
    )

    print("\nservices")
    ux.table(
        ["name", "capability", "port"],
        [
            [service["name"], service["capability"] or "-", str(service["port"] or "-")]
            for service in graph["services"]
        ],
    )
    return 0


def write_docs(args: argparse.Namespace) -> int:
    root = find_template(args.source)
    rendered = render_all(scan(root))
    for name, content in rendered.items():
        (root / name).write_text(content, encoding="utf-8")
    ux.success(f"wrote {', '.join(sorted(rendered))}")
    return 0


def check(args: argparse.Namespace) -> int:
    root = find_template(args.source)
    problems = []

    for name, content in render_all(scan(root)).items():
        path = root / name
        if not path.exists():
            problems.append(f"{name} is missing — run 'genesis docs'")
        elif path.read_text(encoding="utf-8") != content:
            problems.append(f"{name} is stale — run 'genesis docs'")

    types = root / "frontend" / "src" / "lib" / "api-types.ts"
    if types.exists():
        live = _live_schema(args.url)
        if live is None:
            ux.info(f"no app at {args.url}; skipped api-types.ts freshness check")
        elif not _types_match(types.read_text(encoding="utf-8"), live):
            problems.append("frontend/src/lib/api-types.ts is stale — run 'npm run types'")

    for problem in problems:
        ux.error(problem)
    if problems:
        return 1
    ux.success("check passed")
    return 0


def _live_schema(url: str) -> dict | None:
    import json
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return json.loads(response.read())
    except (urllib.error.URLError, OSError, ValueError):
        return None


def _types_match(generated: str, schema: dict) -> bool:
    return all(name in generated for name in schema.get("components", {}).get("schemas", {}))


def run_dev(args: argparse.Namespace) -> int:
    root = find_template(args.source)
    if args.local:
        return dev_local(root)
    with ux.spinner("building and starting the app…"):
        return dev(root, build=not args.no_build)


def run_build(args: argparse.Namespace) -> int:
    root = find_template(args.source)
    with ux.spinner("building the image…"):
        return build(root)


def run_down(args: argparse.Namespace) -> int:
    return down(find_template(args.source))


def run_logs(args: argparse.Namespace) -> int:
    return logs(find_template(args.source))


def run_restart(args: argparse.Namespace) -> int:
    return restart(find_template(args.source), args.process)


def run_migrate(args: argparse.Namespace) -> int:
    return migrate(find_template(args.source), args.message)


def run_deploy(args: argparse.Namespace) -> int:
    return deploy_fly(find_template(args.source), dry_run=args.dry_run, name=args.name)


def list_presets(args: argparse.Namespace) -> int:
    root = find_template(args.source)
    presets = load_presets(root / "modules")
    ux.table(
        ["preset", "summary", "modules"],
        [
            [name, presets[name].get("summary", ""), ", ".join(presets[name]["modules"]) or "none"]
            for name in sorted(presets)
        ],
    )
    return 0


def list_modules(_args: argparse.Namespace) -> int:
    modules = load_modules(find_template(_args.source) / "modules")
    ux.table(
        ["module", "summary", "requires"],
        [
            [
                name,
                modules[name].get("summary", ""),
                ", ".join(modules[name].get("requires", [])) or "-",
            ]
            for name in sorted(modules)
        ],
    )
    return 0


def doctor(args: argparse.Namespace) -> int:
    checks = run_checks()
    for check in checks:
        if check.present:
            ux.success(f"{check.name} found on PATH")
        elif check.required:
            ux.error(f"{check.name} not found — {check.message}")
        else:
            ux.warning(f"{check.name} not found — {check.message}")

    uv_present = next(check for check in checks if check.name == "uv").present
    if not uv_present:
        interactive = _is_interactive()
        if ux.confirm(
            "Install uv now using the official installer script?",
            default=False,
            non_interactive=not interactive,
        ):
            if install_uv() != 0:
                ux.error("uv installer failed — install it manually and re-run 'genesis doctor'")
                return 1
            ux.success("uv installed — open a new shell so PATH changes take effect")
            uv_present = True

    return 0 if uv_present else 1


def show_completion(args: argparse.Namespace) -> int:
    ux.print_completion_instructions(args.shell)
    return 0


def _print_default_screen() -> None:
    ux.info("genesis — a starter template generator and project manager")
    print()
    print("command groups:")
    print("  create, render                              start a new project")
    print("  generate, destroy, add, remove               modify an existing project")
    print("  dev, build, down, logs, restart, migrate     run the app")
    print("  deploy                                       ship the app to Fly.io")
    print("  map, docs, check, presets, modules, doctor   inspect a project")
    print()
    print("run 'genesis --help' for the full command list, or 'genesis create' to get started")


def _ns(**kwargs) -> argparse.Namespace:
    return argparse.Namespace(**kwargs)


def _required_text(message: str, **kwargs) -> str:
    return ux.ask_text(message, validate=bool, **kwargs)


_INTERACTIVE_COMMANDS = [
    ("create", "create a new project"),
    ("render", "assemble a project from modules"),
    ("generate", "generate a model, endpoint, page, task or admin panel"),
    ("destroy", "remove a generated model, endpoint or page"),
    ("add", "add a module to the current project"),
    ("remove", "remove a module from the current project"),
    ("dev", "build and start the app"),
    ("build", "build the image without starting it"),
    ("down", "stop and remove containers"),
    ("logs", "follow container logs"),
    ("restart", "restart one process in the container"),
    ("migrate", "create and apply a migration"),
    ("deploy", "deploy the app to Fly.io"),
    ("map", "print the resolved project graph"),
    ("docs", "generate genesis.json and the AI context docs"),
    ("check", "fail if generated files are stale"),
    ("presets", "list available presets"),
    ("modules", "list available modules"),
    ("doctor", "check local prerequisites for genesis"),
    ("completion", "print shell tab-completion setup instructions"),
]

_GENERATE_COMMANDS = [
    ("scaffold", "a model, endpoint and page together"),
    ("model", "a model file"),
    ("endpoint", "a CRUD endpoint"),
    ("page", "a frontend CRUD page"),
    ("admin", "a data-table admin page for an existing model"),
    ("task", "a background task"),
    ("logger", "add module-logger boilerplate to an existing file"),
]

_DESTROY_COMMANDS = [
    ("scaffold", "the model, endpoint and page together"),
    ("model", "a generated model"),
    ("endpoint", "a generated endpoint"),
    ("page", "a generated page"),
    ("admin", "a generated admin page"),
    ("task", "a generated task"),
]

_DESTROY_PROMPTS = {
    "model": ("Model name to delete:", destroy_model_cmd),
    "endpoint": ("Endpoint name to delete:", destroy_endpoint_cmd),
    "page": ("Page name to delete:", destroy_page_cmd),
    "admin": ("Admin page name to delete:", destroy_admin_cmd),
    "task": ("Task name to delete:", destroy_task_cmd),
    "scaffold": ("Concept name to delete (model, endpoint and page):", destroy_scaffold_cmd),
}


def _interactive_generate(sub: str) -> int:
    if sub == "model":
        name = _required_text("Model name (singular), e.g. Item:")
        return generate_model_cmd(_ns(name=name, fields=[], target=None, force=False))
    if sub == "endpoint":
        name = _required_text("Model name this endpoint is for:")
        return generate_endpoint_cmd(_ns(name=name, target=None, force=False))
    if sub == "page":
        name = _required_text("Model name, e.g. Item:")
        return generate_page_cmd(_ns(name=name, fields=[], target=None, force=False))
    if sub == "admin":
        name = _required_text("Model name this admin page is for:")
        return generate_admin_cmd(_ns(name=name, target=None, force=False))
    if sub == "logger":
        file = _required_text("File to add a logger to, e.g. app/tasks/reports.py:")
        return generate_logger_cmd(_ns(file=file, target=None))
    if sub == "task":
        if ux.confirm("Promote an existing function into a task instead of writing a new one?", default=False):
            source = _required_text(
                "Function to promote, e.g. app/endpoints/items.py:send_alert:"
            )
            return generate_task_cmd(_ns(name=None, fields=[], source=source, target=None, force=False))
        name = _required_text("Task name, e.g. SendAlert:")
        return generate_task_cmd(_ns(name=name, fields=[], source=None, target=None, force=False))
    name = _required_text("Concept name, e.g. Item:")
    return generate_scaffold_cmd(_ns(name=name, fields=[], target=None, force=False))


def _interactive_destroy(sub: str) -> int:
    prompt, handler = _DESTROY_PROMPTS[sub]
    name = _required_text(prompt)
    return handler(_ns(name=name, target=None, force=False))


_NEEDS_TEMPLATE = {
    "create", "render", "add", "remove", "dev", "build", "down", "logs",
    "restart", "migrate", "deploy", "map", "docs", "check", "presets", "modules",
}


def _is_template_path(text: str) -> bool:
    if not text:
        return False
    try:
        find_template(text)
    except ModuleError:
        return False
    return True


def _resolve_source() -> str:
    try:
        return str(find_template(None))
    except ModuleError:
        pass
    return ux.ask_text(
        "Path to your genesis template checkout (the cloned repo, not your new project):",
        validate=_is_template_path,
    )


def _interactive_menu() -> int:
    command = ux.select("What do you want to do?", _INTERACTIVE_COMMANDS)
    source = _resolve_source() if command in _NEEDS_TEMPLATE else None

    if command == "create":
        name = _required_text("Project name:")
        return create(
            _ns(name=name, out=None, preset=None, without=[], topology="single", force=False, source=source)
        )
    if command == "render":
        out = _required_text("Output directory:")
        return render(_ns(out=out, without=[], topology="single", force=False, source=source))
    if command == "generate":
        return _interactive_generate(ux.select("Generate what?", _GENERATE_COMMANDS))
    if command == "destroy":
        return _interactive_destroy(ux.select("Destroy what?", _DESTROY_COMMANDS))
    if command == "add":
        return add_module(_ns(module=None, target=None, source=source))
    if command == "remove":
        return remove_module(_ns(module=None, target=None, source=source))
    if command == "dev":
        local = ux.confirm("Run without Docker (local mode)?", default=False)
        no_build = not local and ux.confirm("Skip the image rebuild?", default=False)
        return run_dev(_ns(source=source, local=local, no_build=no_build))
    if command == "build":
        return run_build(_ns(source=source))
    if command == "down":
        return run_down(_ns(source=source))
    if command == "logs":
        return run_logs(_ns(source=source))
    if command == "restart":
        process = ux.ask_text("Process to restart:", default="fastapi")
        return run_restart(_ns(process=process, source=source))
    if command == "migrate":
        message = _required_text("Migration message:")
        return run_migrate(_ns(message=message, source=source))
    if command == "deploy":
        dry_run = ux.confirm(
            "Dry run (print the deploy command without running it)?", default=False
        )
        return run_deploy(_ns(source=source, name=None, dry_run=dry_run))
    if command == "map":
        return show_map(_ns(source=source))
    if command == "docs":
        return write_docs(_ns(source=source))
    if command == "check":
        return check(_ns(source=source, url="http://localhost:8000/api/openapi.json"))
    if command == "presets":
        return list_presets(_ns(source=source))
    if command == "modules":
        return list_modules(_ns(source=source))
    if command == "doctor":
        return doctor(_ns())
    shell = ux.select("Shell:", ["bash", "zsh", "powershell"])
    return show_completion(_ns(shell=shell))


def main() -> int:
    parser = argparse.ArgumentParser(prog="genesis")
    commands = parser.add_subparsers(dest="command", required=True)

    render_parser = commands.add_parser("render", help="assemble a project from modules")
    render_parser.add_argument("--out", required=True)
    render_parser.add_argument("--without", action="append", default=[], metavar="MODULE")
    render_parser.add_argument("--topology", choices=["single", "compose"], default="single")
    render_parser.add_argument("--force", action="store_true")
    render_parser.add_argument("--source", default=None, metavar="PATH")
    render_parser.set_defaults(handler=render)

    modules_parser = commands.add_parser("modules", help="list available modules")
    modules_parser.add_argument("--source", default=None, metavar="PATH")
    modules_parser.set_defaults(handler=list_modules)

    create_parser = commands.add_parser("create", help="create a new project")
    create_parser.add_argument("name")
    create_parser.add_argument("--out", default=None, metavar="DIR")
    create_parser.add_argument("--preset", default=None)
    create_parser.add_argument("--without", action="append", default=[], metavar="MODULE")
    create_parser.add_argument("--topology", choices=["single", "compose"], default="single")
    create_parser.add_argument("--force", action="store_true")
    create_parser.add_argument("--source", default=None, metavar="PATH")
    create_parser.set_defaults(handler=create)

    generate_parser = commands.add_parser(
        "generate", aliases=["g"], help="generate a model, endpoint or page"
    )
    generate_commands = generate_parser.add_subparsers(dest="generate_command", required=True)

    gen_model = generate_commands.add_parser("model", help="generate a model file")
    gen_model.add_argument("name", help="singular concept name, e.g. Item or BlogPost")
    gen_model.add_argument("fields", nargs="*", help="name:type pairs, e.g. name:string price:float")
    gen_model.add_argument("--target", default=None, metavar="PATH")
    gen_model.add_argument("--force", action="store_true")
    gen_model.set_defaults(handler=generate_model_cmd)

    gen_endpoint = generate_commands.add_parser("endpoint", help="generate a CRUD endpoint")
    gen_endpoint.add_argument("name", help="singular concept name matching an existing model")
    gen_endpoint.add_argument("--target", default=None, metavar="PATH")
    gen_endpoint.add_argument("--force", action="store_true")
    gen_endpoint.set_defaults(handler=generate_endpoint_cmd)

    gen_page = generate_commands.add_parser("page", help="generate a frontend CRUD page")
    gen_page.add_argument("name", help="singular concept name, e.g. Item or BlogPost")
    gen_page.add_argument("fields", nargs="*", help="name:type pairs, e.g. name:string price:float")
    gen_page.add_argument("--target", default=None, metavar="PATH")
    gen_page.add_argument("--force", action="store_true")
    gen_page.set_defaults(handler=generate_page_cmd)

    gen_admin = generate_commands.add_parser(
        "admin", help="generate a data-table admin page for an existing model"
    )
    gen_admin.add_argument("name", help="singular concept name matching an existing model")
    gen_admin.add_argument("--target", default=None, metavar="PATH")
    gen_admin.add_argument("--force", action="store_true")
    gen_admin.set_defaults(handler=generate_admin_cmd)

    gen_task = generate_commands.add_parser("task", help="generate a background task")
    gen_task.add_argument(
        "name", nargs="?", default=None, help="singular concept name, e.g. SendAlert"
    )
    gen_task.add_argument("fields", nargs="*", help="name:type pairs, e.g. count:int label:string")
    gen_task.add_argument(
        "--source",
        default=None,
        metavar="FILE:FUNC",
        help="promote an existing function instead, e.g. app/endpoints/items.py:send_alert",
    )
    gen_task.add_argument("--target", default=None, metavar="PATH")
    gen_task.add_argument("--force", action="store_true")
    gen_task.set_defaults(handler=generate_task_cmd)

    gen_logger = generate_commands.add_parser(
        "logger", help="add module-logger boilerplate to an existing file"
    )
    gen_logger.add_argument("file", help="path to an existing .py file, e.g. app/tasks/reports.py")
    gen_logger.add_argument("--target", default=None, metavar="PATH")
    gen_logger.set_defaults(handler=generate_logger_cmd)

    gen_scaffold = generate_commands.add_parser(
        "scaffold", help="generate a model, endpoint and page together"
    )
    gen_scaffold.add_argument("name", help="singular concept name, e.g. Item or BlogPost")
    gen_scaffold.add_argument(
        "fields", nargs="*", help="name:type pairs, e.g. name:string price:float"
    )
    gen_scaffold.add_argument("--target", default=None, metavar="PATH")
    gen_scaffold.add_argument("--force", action="store_true")
    gen_scaffold.set_defaults(handler=generate_scaffold_cmd)

    destroy_parser = commands.add_parser(
        "destroy", aliases=["d"], help="remove a generated model, endpoint or page"
    )
    destroy_commands = destroy_parser.add_subparsers(dest="destroy_command", required=True)

    destroy_model_parser = destroy_commands.add_parser("model", help="delete a generated model")
    destroy_model_parser.add_argument("name")
    destroy_model_parser.add_argument("--target", default=None, metavar="PATH")
    destroy_model_parser.add_argument("--force", "-y", action="store_true")
    destroy_model_parser.set_defaults(handler=destroy_model_cmd)

    destroy_endpoint_parser = destroy_commands.add_parser(
        "endpoint", help="delete a generated endpoint"
    )
    destroy_endpoint_parser.add_argument("name")
    destroy_endpoint_parser.add_argument("--target", default=None, metavar="PATH")
    destroy_endpoint_parser.add_argument("--force", "-y", action="store_true")
    destroy_endpoint_parser.set_defaults(handler=destroy_endpoint_cmd)

    destroy_page_parser = destroy_commands.add_parser("page", help="delete a generated page")
    destroy_page_parser.add_argument("name")
    destroy_page_parser.add_argument("--target", default=None, metavar="PATH")
    destroy_page_parser.add_argument("--force", "-y", action="store_true")
    destroy_page_parser.set_defaults(handler=destroy_page_cmd)

    destroy_admin_parser = destroy_commands.add_parser("admin", help="delete a generated admin page")
    destroy_admin_parser.add_argument("name")
    destroy_admin_parser.add_argument("--target", default=None, metavar="PATH")
    destroy_admin_parser.add_argument("--force", "-y", action="store_true")
    destroy_admin_parser.set_defaults(handler=destroy_admin_cmd)

    destroy_task_parser = destroy_commands.add_parser("task", help="delete a generated task")
    destroy_task_parser.add_argument("name")
    destroy_task_parser.add_argument("--target", default=None, metavar="PATH")
    destroy_task_parser.add_argument("--force", "-y", action="store_true")
    destroy_task_parser.set_defaults(handler=destroy_task_cmd)

    destroy_scaffold_parser = destroy_commands.add_parser(
        "scaffold", help="delete a generated model, endpoint and page together"
    )
    destroy_scaffold_parser.add_argument("name")
    destroy_scaffold_parser.add_argument("--target", default=None, metavar="PATH")
    destroy_scaffold_parser.add_argument("--force", "-y", action="store_true")
    destroy_scaffold_parser.set_defaults(handler=destroy_scaffold_cmd)

    add_parser = commands.add_parser("add", help="add a module to the current project")
    add_parser.add_argument("module", nargs="?", default=None)
    add_parser.add_argument("--target", default=None, metavar="PATH")
    add_parser.add_argument("--source", default=None, metavar="PATH")
    add_parser.set_defaults(handler=add_module)

    remove_parser = commands.add_parser("remove", help="remove a module from the current project")
    remove_parser.add_argument("module", nargs="?", default=None)
    remove_parser.add_argument("--target", default=None, metavar="PATH")
    remove_parser.add_argument("--source", default=None, metavar="PATH")
    remove_parser.set_defaults(handler=remove_module)

    presets_parser = commands.add_parser("presets", help="list available presets")
    presets_parser.add_argument("--source", default=None, metavar="PATH")
    presets_parser.set_defaults(handler=list_presets)

    map_parser = commands.add_parser("map", help="print the resolved project graph")
    map_parser.add_argument("--source", default=None, metavar="PATH")
    map_parser.set_defaults(handler=show_map)

    docs_parser = commands.add_parser("docs", help="generate genesis.json and the AI context docs")
    docs_parser.add_argument("--source", default=None, metavar="PATH")
    docs_parser.set_defaults(handler=write_docs)

    check_parser = commands.add_parser("check", help="fail if generated files are stale")
    check_parser.add_argument("--source", default=None, metavar="PATH")
    check_parser.add_argument(
        "--url", default="http://localhost:8000/api/openapi.json", metavar="URL"
    )
    check_parser.set_defaults(handler=check)

    dev_parser = commands.add_parser("dev", help="build and start the app")
    dev_parser.add_argument("--source", default=None, metavar="PATH")
    dev_parser.add_argument("--no-build", action="store_true", help="skip the image rebuild")
    dev_parser.add_argument(
        "--local",
        action="store_true",
        help="run without Docker: local Postgres/Temporal via uv, embedded cache",
    )
    dev_parser.set_defaults(handler=run_dev)

    build_parser = commands.add_parser("build", help="build the image without starting it")
    build_parser.add_argument("--source", default=None, metavar="PATH")
    build_parser.set_defaults(handler=run_build)

    down_parser = commands.add_parser("down", help="stop and remove containers")
    down_parser.add_argument("--source", default=None, metavar="PATH")
    down_parser.set_defaults(handler=run_down)

    logs_parser = commands.add_parser("logs", help="follow container logs")
    logs_parser.add_argument("--source", default=None, metavar="PATH")
    logs_parser.set_defaults(handler=run_logs)

    restart_parser = commands.add_parser("restart", help="restart one process in the container")
    restart_parser.add_argument("process", nargs="?", default="fastapi")
    restart_parser.add_argument("--source", default=None, metavar="PATH")
    restart_parser.set_defaults(handler=run_restart)

    migrate_parser = commands.add_parser("migrate", help="create and apply a migration")
    migrate_parser.add_argument("message")
    migrate_parser.add_argument("--source", default=None, metavar="PATH")
    migrate_parser.set_defaults(handler=run_migrate)

    deploy_parser = commands.add_parser("deploy", help="deploy the app to Fly.io")
    deploy_parser.add_argument("--source", default=None, metavar="PATH")
    deploy_parser.add_argument(
        "--name", default=None, metavar="APP", help="Fly app name (defaults to APP_NAME in .env)"
    )
    deploy_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="generate fly.toml and print the deploy command without running it",
    )
    deploy_parser.set_defaults(handler=run_deploy)

    doctor_parser = commands.add_parser("doctor", help="check local prerequisites for genesis")
    doctor_parser.set_defaults(handler=doctor)

    completion_parser = commands.add_parser(
        "completion", help="print shell tab-completion setup instructions"
    )
    completion_parser.add_argument("shell", choices=["bash", "zsh", "powershell"])
    completion_parser.set_defaults(handler=show_completion)

    ux.enable_completion(parser)
    if len(sys.argv) == 1:
        if not _is_interactive():
            _print_default_screen()
            return 0
        handler = _interactive_menu
    else:
        args = parser.parse_args()
        handler = functools.partial(args.handler, args)

    try:
        return handler()
    except (
        ModuleError,
        MarkerError,
        OpsError,
        LocalError,
        SyncError,
        FieldError,
        GenerateError,
        DeployError,
    ) as exc:
        ux.error(str(exc))
        return 1
    except ux.PromptCancelled:
        ux.warning("cancelled")
        return 1
    except ux.NonInteractiveError as exc:
        ux.error(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
