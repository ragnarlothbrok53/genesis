import ast
import builtins
import sys
from pathlib import Path

from genesis_cli.fields import FieldSpec, create_field, peewee_field, python_type
from genesis_cli.inflect import pascal_case, pluralize, snake_case, title_case


class GenerateError(Exception):
    pass


def _target_root(path: Path) -> Path:
    if not (path / "modules" / "kernel.toml").is_file():
        raise GenerateError(f"{path} is not a genesis project (no modules/kernel.toml)")
    return path


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        raise GenerateError(f"{path} already exists — pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def render_model(class_name: str, table_name: str, fields: list[FieldSpec]) -> str:
    reference_targets = sorted({field.target for field in fields if field.kind == "references"})
    lines = [
        "from datetime import datetime",
        "",
        "from pydantic import BaseModel, Field",
        "",
    ]
    for target in reference_targets:
        lines.append(f"from app.models.{snake_case(target)} import {target}")
    lines.append("from genesis import db")
    lines += ["", "", f"class {class_name}(db.Model):"]
    for field in fields:
        lines.append(f"    {field.name} = {peewee_field(field)}")
    lines.append("    created_at = db.DateTime(default=db.now)")
    lines += ["", "    class Meta:", f'        table_name = "{table_name}"', "", ""]

    lines.append(f"class {class_name}Create(BaseModel):")
    lines += [f"    {field.name}: {create_field(field)}" for field in fields] or ["    pass"]
    lines += ["", ""]

    lines.append(f"class {class_name}Read(BaseModel):")
    lines.append("    id: int")
    lines += [f"    {field.name}: {python_type(field)}" for field in fields]
    lines.append("    created_at: datetime")
    lines += ["", ""]

    lines.append(f"class {class_name}Update(BaseModel):")
    lines += [
        f"    {field.name}: {python_type(field, force_optional=True)} = None" for field in fields
    ] or ["    pass"]

    return "\n".join(lines) + "\n"


def render_endpoint(resource: str, class_name: str, model_module: str) -> str:
    singular = snake_case(class_name)
    pk = f"{singular}_id"
    return f'''from fastapi import HTTPException

from app.models.{model_module} import {class_name}, {class_name}Create, {class_name}Read, {class_name}Update
from genesis import db, router

api = router("/{resource}")


@api.get("", response_model=list[{class_name}Read])
def list_{resource}():
    return list({class_name}.select().order_by({class_name}.id).dicts())


@api.get("/{{{pk}}}", response_model={class_name}Read)
def get_{singular}({pk}: int):
    {singular} = {class_name}.get_or_none({class_name}.id == {pk})
    if {singular} is None:
        raise HTTPException(status_code=404, detail="{class_name} not found")
    return db.to_dict({singular})


@api.post("", response_model={class_name}Read, status_code=201)
def create_{singular}(payload: {class_name}Create):
    return db.to_dict({class_name}.create(**payload.model_dump()))


@api.patch("/{{{pk}}}", response_model={class_name}Read)
def update_{singular}({pk}: int, payload: {class_name}Update):
    {singular} = {class_name}.get_or_none({class_name}.id == {pk})
    if {singular} is None:
        raise HTTPException(status_code=404, detail="{class_name} not found")
    changes = payload.model_dump(exclude_unset=True)
    if changes:
        {class_name}.update(**changes).where({class_name}.id == {pk}).execute()
        {singular} = {class_name}.get_by_id({pk})
    return db.to_dict({singular})


@api.delete("/{{{pk}}}", status_code=204)
def delete_{singular}({pk}: int):
    if not {class_name}.delete_by_id({pk}):
        raise HTTPException(status_code=404, detail="{class_name} not found")
'''


def _input_for(field: FieldSpec) -> str:
    if field.kind in ("int", "integer", "float", "references"):
        return "number"
    if field.kind in ("bool", "boolean"):
        return "checkbox"
    return "text"


def _default_state(field: FieldSpec) -> str:
    return "false" if field.kind in ("bool", "boolean") else '""'


def _payload_value(field: FieldSpec, obj: str = "form") -> str:
    if field.kind in ("int", "integer", "float", "references"):
        return f"{obj}.{field.name} === '' ? undefined : Number({obj}.{field.name})"
    if field.kind in ("bool", "boolean"):
        return f"{obj}.{field.name}"
    return f"{obj}.{field.name} || undefined"


def _cell_value(field: FieldSpec, obj: str = "item") -> str:
    if field.kind in ("bool", "boolean"):
        return f"{obj}.{field.name} ? 'yes' : 'no'"
    if field.kind == "datetime":
        return f"new Date({obj}.{field.name}).toLocaleString()"
    return f"{obj}.{field.name}"


def _render_input(field: FieldSpec, obj: str = "form", setter: str = "setForm") -> str:
    input_type = _input_for(field)
    if input_type == "checkbox":
        return (
            f'          <label className="flex items-center gap-2 text-sm">'
            f'<input type="checkbox" checked={{{obj}.{field.name}}}'
            f" onChange={{(e) => {setter}({{ ...{obj}, {field.name}: e.target.checked }})}} />"
            f" {title_case(field.name)}</label>"
        )
    return (
        f'          <Input placeholder="{title_case(field.name)}" type="{input_type}"'
        f" value={{{obj}.{field.name}}}"
        f" onChange={{(e) => {setter}({{ ...{obj}, {field.name}: e.target.value }})}} />"
    )


def render_page(resource: str, class_name: str, page_name: str, fields: list[FieldSpec]) -> str:
    formable = [field for field in fields if field.kind != "datetime"]

    state_entries = ", ".join(f"{field.name}: {_default_state(field)}" for field in formable)
    reset_entries = state_entries

    inputs = "\n".join(_render_input(field) for field in formable)

    headers = "\n".join(
        f"              <TableHead>{title_case(field.name)}</TableHead>" for field in fields
    )
    cells = "\n".join(
        f"                <TableCell>{{{_cell_value(field)}}}</TableCell>" for field in fields
    )
    payload = ",\n".join(f"      {field.name}: {_payload_value(field)}" for field in formable)

    return f'''import {{ useCallback, useEffect, useState }} from "react"
import {{ LayoutGrid, Plus, Trash2 }} from "lucide-react"

import {{ api, type Schema }} from "@/lib/api"
import {{ Button }} from "@/components/ui/button"
import {{ Card, CardContent, CardDescription, CardHeader, CardTitle }} from "@/components/ui/card"
import {{ Input }} from "@/components/ui/input"
import {{ Table, TableBody, TableCell, TableHead, TableHeader, TableRow }} from "@/components/ui/table"

type {class_name} = Schema<"{class_name}Read">

export const route = "/{resource}"
export const nav = {{ label: "{page_name}", icon: LayoutGrid }}

export default function {page_name.replace(" ", "")}() {{
  const [items, setItems] = useState<{class_name}[]>([])
  const [form, setForm] = useState({{ {state_entries} }})

  const load = useCallback(() => api.get<{class_name}[]>("/api/v1/{resource}").then(setItems), [])
  useEffect(() => {{
    load()
  }}, [load])

  const add = async () => {{
    await api.post("/api/v1/{resource}", {{
{payload}
    }})
    setForm({{ {reset_entries} }})
    load()
  }}

  const remove = async (id: number) => {{
    await api.del(`/api/v1/{resource}/${{id}}`)
    load()
  }}

  return (
    <Card>
      <CardHeader>
        <CardTitle>{page_name}</CardTitle>
        <CardDescription>Generated by genesis generate scaffold</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
{inputs}
          <Button onClick={{add}}>
            <Plus /> Add
          </Button>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
{headers}
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {{items.map((item) => (
              <TableRow key={{item.id}}>
{cells}
                <TableCell>
                  <Button variant="ghost" size="icon" onClick={{() => remove(item.id)}}>
                    <Trash2 />
                  </Button>
                </TableCell>
              </TableRow>
            ))}}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}}
'''


def _sample_literal(field: FieldSpec) -> str:
    if field.kind == "string":
        return f'"test-{field.name}"'
    if field.kind == "text":
        return f'"{field.name} text"'
    if field.kind in ("int", "integer", "references"):
        return "1"
    if field.kind == "float":
        return "1.5"
    if field.kind in ("bool", "boolean"):
        return "True"
    return '"2024-01-01T00:00:00"'


def _payload_block(
    fields: list[FieldSpec],
    entry_indent: str,
    close_indent: str,
    blank: str | None = None,
    omit: str | None = None,
) -> str:
    entries = []
    for field in fields:
        if field.name == omit:
            continue
        value = '""' if field.name == blank else _sample_literal(field)
        entries.append(f'{entry_indent}"{field.name}": {value},')
    if not entries:
        return "{}"
    return "{\n" + "\n".join(entries) + f"\n{close_indent}}}"


def render_test(resource: str, class_name: str, fields: list[FieldSpec]) -> str:
    singular = snake_case(class_name)
    payload = _payload_block(fields, "            ", "        ")
    field_names = [field.name for field in fields]
    key_set = "{" + ", ".join(f'"{n}"' for n in ["id", *field_names, "created_at"]) + "}"
    delete_expr = f'client.delete(f"/api/v1/{resource}/{{{singular}[\'id\']}}")'

    lines = [
        "import os",
        "",
        "import httpx",
        "import pytest",
        "",
        'BASE_URL = os.getenv("GENESIS_URL", "http://localhost:8000")',
        "",
        "",
        '@pytest.fixture(scope="module")',
        "def client():",
        "    with httpx.Client(base_url=BASE_URL, timeout=15.0) as http:",
        "        try:",
        '            http.get("/api/health")',
        "        except httpx.HTTPError:",
        '            pytest.skip(f"no app running at {BASE_URL}")',
        "        yield http",
        "",
        "",
        f"def test_{singular}_lifecycle(client):",
        "    created = client.post(",
        f'        "/api/v1/{resource}",',
        f"        json={payload},",
        "    )",
        "    assert created.status_code == 201",
        f"    {singular} = created.json()",
    ]
    if field_names:
        first = fields[0]
        lines.append(f'    assert {singular}["{first.name}"] == {_sample_literal(first)}')
    lines += [
        f"    assert set({singular}) == {key_set}",
        "",
        f'    listed = client.get("/api/v1/{resource}").json()',
        f'    assert any(row["id"] == {singular}["id"] for row in listed)',
        "",
        f"    assert {delete_expr}.status_code == 204",
        f"    assert {delete_expr}.status_code == 404",
    ]

    required = next((field for field in fields if not field.nullable), None)
    if required is not None:
        if required.kind in ("string", "text"):
            bad_payload = _payload_block(fields, "            ", "        ", blank=required.name)
            test_name = f"test_{singular}_rejects_blank_{required.name}"
        else:
            bad_payload = _payload_block(fields, "            ", "        ", omit=required.name)
            test_name = f"test_{singular}_rejects_missing_{required.name}"
        lines += [
            "",
            "",
            f"def {test_name}(client):",
            "    response = client.post(",
            f'        "/api/v1/{resource}",',
            f"        json={bad_payload},",
            "    )",
            "    assert response.status_code == 422",
        ]

    return "\n".join(lines) + "\n"


_ANNOTATION_KINDS = {"str": "string", "int": "int", "float": "float", "bool": "bool", "datetime": "datetime"}


def _kind_from_annotation(annotation: str) -> tuple[str, bool]:
    nullable = annotation.endswith("| None")
    base = annotation.removesuffix("| None").strip()
    return _ANNOTATION_KINDS.get(base, "string"), nullable


def _read_model_fields(model_source: str, class_name: str) -> list[FieldSpec]:
    tree = ast.parse(model_source)
    read_class = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == f"{class_name}Read"
        ),
        None,
    )
    if read_class is None:
        raise GenerateError(f"could not find class {class_name}Read in the model file")

    fields = []
    for stmt in read_class.body:
        if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
            continue
        name = stmt.target.id
        if name in ("id", "created_at"):
            continue
        kind, nullable = _kind_from_annotation(ast.unparse(stmt.annotation))
        fields.append(FieldSpec(name=name, kind=kind, nullable=nullable))
    return fields


def _endpoint_supports_patch(endpoint_source: str) -> bool:
    tree = ast.parse(endpoint_source)
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if not (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)):
                continue
            if decorator.func.attr in ("patch", "put"):
                return True
    return False


def render_admin_page(
    resource: str, class_name: str, page_name: str, fields: list[FieldSpec], editable: bool
) -> str:
    component_name = f"Admin{page_name.replace(' ', '')}"
    headers = "\n".join(
        f"              <TableHead>{title_case(field.name)}</TableHead>" for field in fields
    )

    if editable:
        state_entries = ", ".join(f"{field.name}: {_default_state(field)}" for field in fields)
        draft_entries = ", ".join(
            (f"{field.name}: row.{field.name}" if field.kind in ("bool", "boolean") else f"{field.name}: String(row.{field.name} ?? '')")
            for field in fields
        )
        payload = ",\n".join(f"      {field.name}: {_payload_value(field, 'draft')}" for field in fields)
        cells = "\n".join(
            f"""                <TableCell>
                  {{editingId === item.id ? (
{_render_input(field, "draft", "setDraft")}
                  ) : (
                    {_cell_value(field)}
                  )}}
                </TableCell>"""
            for field in fields
        )
        actions = '''                  {editingId === item.id ? (
                    <>
                      <Button variant="ghost" size="icon" onClick={() => save(item.id)}>
                        <Save />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={cancelEdit}>
                        <X />
                      </Button>
                    </>
                  ) : (
                    <>
                      <Button variant="ghost" size="icon" onClick={() => startEdit(item)}>
                        <Pencil />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => remove(item.id)}>
                        <Trash2 />
                      </Button>
                    </>
                  )}'''
        state_block = f'''  const [editingId, setEditingId] = useState<number | null>(null)
  const [draft, setDraft] = useState({{ {state_entries} }})

  const startEdit = (row: {class_name}) => {{
    setEditingId(row.id)
    setDraft({{ {draft_entries} }})
  }}

  const cancelEdit = () => setEditingId(null)

  const save = async (id: number) => {{
    await api.patch(`/api/v1/{resource}/${{id}}`, {{
{payload}
    }})
    setEditingId(null)
    load()
  }}

'''
        icons = "Pencil, Save, Trash2, X"
    else:
        cells = "\n".join(
            f"                <TableCell>{{{_cell_value(field)}}}</TableCell>" for field in fields
        )
        actions = '''                  <Button variant="ghost" size="icon" onClick={() => remove(item.id)}>
                    <Trash2 />
                  </Button>'''
        state_block = ""
        icons = "Trash2"

    limitation = (
        ""
        if editable
        else "\n        <p className=\"text-sm text-muted-foreground\">"
        "Inline edit is unavailable — the /api/v1/"
        f"{resource} endpoint has no PATCH/PUT route. Delete only.</p>"
    )

    uses_input = editable and any(field.kind not in ("bool", "boolean") for field in fields)
    input_import = '\nimport { Input } from "@/components/ui/input"' if uses_input else ""

    return f'''import {{ useCallback, useEffect, useState }} from "react"
import {{ LayoutGrid, {icons} }} from "lucide-react"

import {{ api, type Schema }} from "@/lib/api"
import {{ Button }} from "@/components/ui/button"
import {{ Card, CardContent, CardDescription, CardHeader, CardTitle }} from "@/components/ui/card"{input_import}
import {{ Table, TableBody, TableCell, TableHead, TableHeader, TableRow }} from "@/components/ui/table"

type {class_name} = Schema<"{class_name}Read">

export const route = "/admin/{resource}"
export const nav = {{ label: "{page_name} Admin", icon: LayoutGrid }}

export default function {component_name}() {{
  const [items, setItems] = useState<{class_name}[]>([])
{state_block}
  const load = useCallback(() => api.get<{class_name}[]>("/api/v1/{resource}").then(setItems), [])
  useEffect(() => {{
    load()
  }}, [load])

  const remove = async (id: number) => {{
    await api.del(`/api/v1/{resource}/${{id}}`)
    load()
  }}

  return (
    <Card>
      <CardHeader>
        <CardTitle>{page_name} Admin</CardTitle>
        <CardDescription>Generated by genesis generate admin</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">{limitation}
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
{headers}
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {{items.map((item) => (
              <TableRow key={{item.id}}>
                <TableCell>{{item.id}}</TableCell>
{cells}
                <TableCell className="flex gap-1">
{actions}
                </TableCell>
              </TableRow>
            ))}}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}}
'''


def render_task(func_name: str, fields: list[FieldSpec]) -> str:
    params = ", ".join(f"{field.name}: {python_type(field)}" for field in fields)
    return f'''from genesis import task


@task
def {func_name}({params}) -> str:
    raise NotImplementedError("{func_name}: fill in the logic")
'''


def _is_stdlib_import(import_line: str) -> bool:
    module = import_line.split()[1].split(".")[0]
    return module in sys.stdlib_module_names


def _module_imports(tree: ast.Module) -> tuple[dict[str, str], set[str]]:
    imports: dict[str, str] = {}
    relative: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                asname = f" as {alias.asname}" if alias.asname else ""
                imports[bound] = f"import {alias.name}{asname}"
        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            for alias in node.names:
                bound = alias.asname or alias.name
                asname = f" as {alias.asname}" if alias.asname else ""
                imports[bound] = f"from {module} import {alias.name}{asname}"
                if node.level > 0:
                    relative.add(bound)
    return imports, relative


def _param_names(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    args = func_node.args
    names = {arg.arg for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs)}
    if args.vararg:
        names.add(args.vararg.arg)
    if args.kwarg:
        names.add(args.kwarg.arg)
    return names


def _referenced_names(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    args = func_node.args
    parts: list[ast.AST] = list(func_node.body)
    if func_node.returns is not None:
        parts.append(func_node.returns)
    for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs):
        if arg.annotation is not None:
            parts.append(arg.annotation)
    if args.vararg and args.vararg.annotation is not None:
        parts.append(args.vararg.annotation)
    if args.kwarg and args.kwarg.annotation is not None:
        parts.append(args.kwarg.annotation)
    parts += args.defaults + args.kw_defaults
    return {node.id for part in parts for node in ast.walk(part) if isinstance(node, ast.Name)}


def _find_function(
    tree: ast.Module, func_name: str
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == func_name:
            return node
    return None


def _split_source_spec(spec: str) -> tuple[str, str]:
    if ":" not in spec:
        raise GenerateError(
            f"'{spec}' is not path:function — e.g. backend/app/endpoints/items.py:some_function"
        )
    path_part, func_name = spec.rsplit(":", 1)
    if not func_name.isidentifier():
        raise GenerateError(f"'{func_name}' is not a valid function name")
    return path_part, func_name


def _model_path(target: Path, name: str) -> Path:
    return target / "backend" / "app" / "models" / f"{snake_case(name)}.py"


def _endpoint_path(target: Path, name: str) -> Path:
    return target / "backend" / "app" / "endpoints" / f"{pluralize(snake_case(name))}.py"


def _page_path(target: Path, name: str) -> Path:
    return target / "frontend" / "src" / "pages" / f"{pascal_case(pluralize(snake_case(name)))}.tsx"


def _test_path(target: Path, name: str) -> Path:
    return target / "backend" / "tests" / f"test_{pluralize(snake_case(name))}.py"


def _admin_page_path(target: Path, name: str) -> Path:
    return target / "frontend" / "src" / "pages" / f"Admin{pascal_case(pluralize(snake_case(name)))}.tsx"


def _tasks_dir(target: Path) -> Path:
    return target / "backend" / "app" / "tasks"


def _task_path(target: Path, name: str) -> Path:
    return _tasks_dir(target) / f"{snake_case(name)}.py"


def generate_model(target: Path, name: str, fields: list[FieldSpec], force: bool = False) -> Path:
    target = _target_root(target)
    class_name = pascal_case(name)
    table_name = pluralize(snake_case(name))

    for field in fields:
        if field.kind == "references":
            target_model = _model_path(target, field.target)
            if not target_model.exists():
                raise GenerateError(
                    f"{target_model} does not exist — '{field.name}:references' needs "
                    f"'{field.target}' to exist first; run 'genesis generate model {field.target}'"
                )

    path = _model_path(target, name)
    _write(path, render_model(class_name, table_name, fields), force)
    return path


def generate_endpoint(target: Path, name: str, force: bool = False) -> Path:
    target = _target_root(target)
    class_name = pascal_case(name)
    model_snake = snake_case(name)
    resource = pluralize(model_snake)

    model_path = _model_path(target, name)
    if not model_path.exists():
        raise GenerateError(
            f"{model_path} does not exist — run 'genesis generate model {name}' first"
        )

    path = _endpoint_path(target, name)
    _write(path, render_endpoint(resource, class_name, model_snake), force)
    return path


def generate_page(target: Path, name: str, fields: list[FieldSpec], force: bool = False) -> Path:
    target = _target_root(target)
    class_name = pascal_case(name)
    resource = pluralize(snake_case(name))
    page_name = title_case(resource)

    path = _page_path(target, name)
    _write(path, render_page(resource, class_name, page_name, fields), force)
    return path


def generate_test(target: Path, name: str, fields: list[FieldSpec], force: bool = False) -> Path:
    target = _target_root(target)
    class_name = pascal_case(name)
    resource = pluralize(snake_case(name))

    path = _test_path(target, name)
    _write(path, render_test(resource, class_name, fields), force)
    return path


def generate_admin(target: Path, name: str, force: bool = False) -> tuple[Path, bool]:
    target = _target_root(target)
    class_name = pascal_case(name)
    resource = pluralize(snake_case(name))
    page_name = title_case(resource)

    model_path = _model_path(target, name)
    if not model_path.exists():
        raise GenerateError(
            f"{model_path} does not exist — run 'genesis generate model {name}' first"
        )
    endpoint_path = _endpoint_path(target, name)
    if not endpoint_path.exists():
        raise GenerateError(
            f"{endpoint_path} does not exist — run 'genesis generate endpoint {name}' first"
        )

    fields = _read_model_fields(model_path.read_text(encoding="utf-8"), class_name)
    editable = _endpoint_supports_patch(endpoint_path.read_text(encoding="utf-8"))

    path = _admin_page_path(target, name)
    _write(path, render_admin_page(resource, class_name, page_name, fields, editable), force)
    return path, editable


def generate_task(target: Path, name: str, fields: list[FieldSpec], force: bool = False) -> Path:
    target = _target_root(target)
    for field in fields:
        if field.kind == "references":
            raise GenerateError(
                f"'{field.name}:references' doesn't make sense for a task parameter — "
                "a task parameter isn't a database row; pass the id as an int instead"
            )
    if not _tasks_dir(target).is_dir():
        raise GenerateError(
            f"{_tasks_dir(target)} does not exist — run 'genesis add jobs' first"
        )

    path = _task_path(target, name)
    _write(path, render_task(snake_case(name), fields), force)
    return path


def promote_task(target: Path, source_spec: str, force: bool = False) -> tuple[Path, list[str]]:
    target = _target_root(target)
    if not _tasks_dir(target).is_dir():
        raise GenerateError(
            f"{_tasks_dir(target)} does not exist — run 'genesis add jobs' first"
        )

    path_part, func_name = _split_source_spec(source_spec)
    source_path = Path(path_part)
    if not source_path.is_absolute():
        source_path = (target / source_path).resolve()
    if not source_path.exists():
        raise GenerateError(f"{source_path} does not exist")

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    func_node = _find_function(tree, func_name)
    if func_node is None:
        raise GenerateError(f"no top-level function '{func_name}' in {source_path}")

    imports, relative_imports = _module_imports(tree)
    used_names = _referenced_names(func_node)
    param_names = _param_names(func_node)

    needed_import_names = sorted(name for name in imports if name in used_names)
    import_lines = sorted({imports[name] for name in needed_import_names})

    unresolved = sorted(
        used_names - param_names - set(imports) - set(dir(builtins)) - {func_node.name}
    )
    warnings = []
    if unresolved:
        warnings.append(
            f"references names not defined in the new file: {', '.join(unresolved)} — fix these by hand"
        )
    relative_used = sorted(name for name in needed_import_names if name in relative_imports)
    if relative_used:
        warnings.append(
            f"relative import(s) for {', '.join(relative_used)} won't resolve the same way "
            "from backend/app/tasks/ — change to an absolute import"
        )

    func_node.decorator_list = [ast.Name(id="task", ctx=ast.Load())]
    function_source = ast.unparse(ast.fix_missing_locations(func_node))

    all_lines = sorted({*import_lines, "from genesis import task"})
    stdlib_lines = [line for line in all_lines if _is_stdlib_import(line)]
    other_lines = [line for line in all_lines if not _is_stdlib_import(line)]
    header = "\n\n".join("\n".join(group) for group in (stdlib_lines, other_lines) if group)
    content = header + "\n\n\n" + function_source + "\n"

    path = _task_path(target, func_node.name)
    _write(path, content, force)
    return path, warnings


def destroy_task(target: Path, name: str) -> Path:
    target = _target_root(target)
    path = _task_path(target, name)
    if not path.exists():
        raise GenerateError(f"{path} does not exist")
    path.unlink()
    return path


def destroy_test(target: Path, name: str) -> Path:
    target = _target_root(target)
    path = _test_path(target, name)
    if not path.exists():
        raise GenerateError(f"{path} does not exist")
    path.unlink()
    return path


def destroy_model(target: Path, name: str) -> Path:
    target = _target_root(target)
    path = _model_path(target, name)
    if not path.exists():
        raise GenerateError(f"{path} does not exist")
    path.unlink()
    return path


def destroy_endpoint(target: Path, name: str) -> Path:
    target = _target_root(target)
    path = _endpoint_path(target, name)
    if not path.exists():
        raise GenerateError(f"{path} does not exist")
    path.unlink()
    return path


def destroy_page(target: Path, name: str) -> Path:
    target = _target_root(target)
    path = _page_path(target, name)
    if not path.exists():
        raise GenerateError(f"{path} does not exist")
    path.unlink()
    return path


def destroy_admin(target: Path, name: str) -> Path:
    target = _target_root(target)
    path = _admin_page_path(target, name)
    if not path.exists():
        raise GenerateError(f"{path} does not exist")
    path.unlink()
    return path


def destroy_scaffold(target: Path, name: str) -> dict[str, Path]:
    target = _target_root(target)
    removed = {}
    for kind, destroyer in (
        ("model", destroy_model),
        ("endpoint", destroy_endpoint),
        ("page", destroy_page),
        ("test", destroy_test),
    ):
        try:
            removed[kind] = destroyer(target, name)
        except GenerateError:
            continue
    if not removed:
        raise GenerateError(f"nothing to destroy for '{name}' — no model, endpoint or page found")
    return removed


def generate_scaffold(
    target: Path, name: str, fields: list[FieldSpec], force: bool = False
) -> dict[str, Path]:
    target = _target_root(target)
    model_path = generate_model(target, name, fields, force)
    endpoint_path = generate_endpoint(target, name, force)
    page_path = generate_page(target, name, fields, force)
    test_path = generate_test(target, name, fields, force)
    return {"model": model_path, "endpoint": endpoint_path, "page": page_path, "test": test_path}
