import argparse
import ast
from pathlib import Path

import pytest

from genesis_cli.cli import create, destroy_scaffold_cmd, generate_scaffold_cmd
from genesis_cli.fields import parse_fields
from genesis_cli.generate import (
    GenerateError,
    destroy_admin,
    destroy_endpoint,
    destroy_model,
    destroy_page,
    destroy_scaffold,
    destroy_task,
    destroy_test,
    generate_admin,
    generate_endpoint,
    generate_model,
    generate_page,
    generate_scaffold,
    generate_task,
    generate_test,
    promote_task,
)

TEMPLATE = Path(__file__).resolve().parents[3]


def make_project(tmp_path: Path, name: str, preset: str = "api") -> Path:
    out = tmp_path / name
    args = argparse.Namespace(
        name=name,
        out=str(out),
        preset=preset,
        without=[],
        topology="single",
        force=True,
        source=str(TEMPLATE),
    )
    assert create(args) == 0
    return out


def test_generate_model_produces_valid_python(tmp_path):
    project = make_project(tmp_path, "p1")
    fields = parse_fields(["name:string", "price:float", "notes:text?"])
    path = generate_model(project, "Product", fields)

    source = path.read_text(encoding="utf-8")
    module = ast.parse(source)
    classes = {node.name for node in module.body if isinstance(node, ast.ClassDef)}
    assert classes == {"Product", "ProductCreate", "ProductRead", "ProductUpdate"}


def test_generate_model_table_and_field_types(tmp_path):
    project = make_project(tmp_path, "p2")
    fields = parse_fields(["name:string", "in_stock:bool"])
    path = generate_model(project, "Product", fields)
    source = path.read_text(encoding="utf-8")

    assert 'table_name = "products"' in source
    assert "name = db.Char(max_length=200)" in source
    assert "in_stock = db.Bool()" in source
    assert "created_at = db.DateTime(default=db.now)" in source


def test_generate_model_nullable_field_is_optional_everywhere(tmp_path):
    project = make_project(tmp_path, "p3")
    fields = parse_fields(["notes:text?"])
    source = generate_model(project, "Product", fields).read_text(encoding="utf-8")

    assert "notes = db.Text(null=True)" in source
    assert "notes: str | None = None" in source  # in Create
    assert "notes: str | None\n" in source  # in Read


def test_generate_model_update_shape_makes_every_field_optional(tmp_path):
    project = make_project(tmp_path, "p4")
    fields = parse_fields(["name:string", "price:float"])
    source = generate_model(project, "Product", fields).read_text(encoding="utf-8")

    module = ast.parse(source)
    update = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "ProductUpdate"
    )
    for stmt in update.body:
        assert isinstance(stmt, ast.AnnAssign)
        assert isinstance(stmt.value, ast.Constant) and stmt.value.value is None


def test_generate_model_refuses_to_overwrite_without_force(tmp_path):
    project = make_project(tmp_path, "p5")
    generate_model(project, "Product", [])
    with pytest.raises(GenerateError, match="already exists"):
        generate_model(project, "Product", [])


def test_generate_model_force_overwrites(tmp_path):
    project = make_project(tmp_path, "p6")
    generate_model(project, "Product", [])
    generate_model(project, "Product", parse_fields(["sku:string"]), force=True)
    source = (project / "backend" / "app" / "models" / "product.py").read_text(encoding="utf-8")
    assert "sku" in source


def test_generate_endpoint_requires_the_model_first(tmp_path):
    project = make_project(tmp_path, "p7")
    with pytest.raises(GenerateError, match="generate model Product"):
        generate_endpoint(project, "Product")


def test_generate_endpoint_produces_full_crud(tmp_path):
    project = make_project(tmp_path, "p8")
    generate_model(project, "Product", [])
    path = generate_endpoint(project, "Product")
    source = path.read_text(encoding="utf-8")

    module = ast.parse(source)
    decorators = {
        decorator.func.attr
        for node in module.body
        if isinstance(node, ast.FunctionDef)
        for decorator in node.decorator_list
        if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
    }
    assert decorators == {"get", "post", "patch", "delete"}
    assert 'router("/products")' in source


def test_generate_endpoint_every_route_has_a_response_model_or_no_content(tmp_path):
    project = make_project(tmp_path, "p9")
    generate_model(project, "Product", [])
    source = generate_endpoint(project, "Product").read_text(encoding="utf-8")
    module = ast.parse(source)

    for node in module.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if not (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)):
                continue
            keywords = {kw.arg for kw in decorator.keywords}
            status = next(
                (ast.literal_eval(kw.value) for kw in decorator.keywords if kw.arg == "status_code"),
                200,
            )
            assert "response_model" in keywords or status == 204


def test_generate_page_valid_tsx_shape(tmp_path):
    project = make_project(tmp_path, "p10")
    fields = parse_fields(["name:string", "price:float", "in_stock:bool", "released_at:datetime"])
    path = generate_page(project, "Product", fields)
    source = path.read_text(encoding="utf-8")

    assert 'export const route = "/products"' in source
    assert 'Schema<"ProductRead">' in source
    assert source.count("<TableHead>") == 4  # one per field, datetime included in display


def test_generate_page_checkbox_uses_checked_not_value(tmp_path):
    project = make_project(tmp_path, "p11")
    source = generate_page(project, "Product", parse_fields(["in_stock:bool"])).read_text(
        encoding="utf-8"
    )
    assert "checked={form.in_stock}" in source
    assert "value={form.in_stock}" not in source


def test_generate_page_excludes_datetime_from_the_create_form(tmp_path):
    project = make_project(tmp_path, "p12")
    source = generate_page(project, "Product", parse_fields(["released_at:datetime"])).read_text(
        encoding="utf-8"
    )
    assert "form.released_at" not in source
    assert "toLocaleString" in source


def test_generate_test_produces_a_crud_lifecycle_test(tmp_path):
    project = make_project(tmp_path, "p12b")
    fields = parse_fields(["name:string", "price:float"])
    path = generate_test(project, "Product", fields)
    source = path.read_text(encoding="utf-8")

    ast.parse(source)
    assert path == project / "backend" / "tests" / "test_products.py"
    assert "def test_product_lifecycle(client):" in source
    assert '"/api/v1/products"' in source
    assert '"name": "test-name"' in source
    assert '"price": 1.5' in source
    assert 'assert product["name"] == "test-name"' in source
    assert 'assert set(product) == {"id", "name", "price", "created_at"}' in source
    assert "status_code == 201" in source
    assert "status_code == 204" in source
    assert "status_code == 404" in source


def test_generate_test_rejects_blank_required_string_field(tmp_path):
    project = make_project(tmp_path, "p12c")
    source = generate_test(project, "Product", parse_fields(["name:string"])).read_text(
        encoding="utf-8"
    )

    assert "def test_product_rejects_blank_name(client):" in source
    assert '"name": ""' in source
    assert "status_code == 422" in source


def test_generate_test_rejects_missing_required_non_string_field(tmp_path):
    project = make_project(tmp_path, "p12d")
    source = generate_test(project, "Product", parse_fields(["price:float"])).read_text(
        encoding="utf-8"
    )

    assert "def test_product_rejects_missing_price(client):" in source
    assert "json={}" in source


def test_generate_test_skips_rejection_test_when_all_fields_nullable(tmp_path):
    project = make_project(tmp_path, "p12e")
    source = generate_test(project, "Product", parse_fields(["notes:text?"])).read_text(
        encoding="utf-8"
    )

    assert "rejects" not in source


def test_destroy_test_deletes_the_file(tmp_path):
    project = make_project(tmp_path, "p12f")
    path = generate_test(project, "Product", parse_fields(["name:string"]))
    assert path.exists()

    destroy_test(project, "Product")
    assert not path.exists()


def test_generate_admin_requires_the_model_first(tmp_path):
    project = make_project(tmp_path, "a1")
    with pytest.raises(GenerateError, match="generate model Product"):
        generate_admin(project, "Product")


def test_generate_admin_requires_the_endpoint_first(tmp_path):
    project = make_project(tmp_path, "a2")
    generate_model(project, "Product", parse_fields(["name:string"]))
    with pytest.raises(GenerateError, match="generate endpoint Product"):
        generate_admin(project, "Product")


def test_generate_admin_detects_patch_support_from_generated_endpoint(tmp_path):
    project = make_project(tmp_path, "a3")
    generate_model(project, "Product", parse_fields(["name:string", "price:float"]))
    generate_endpoint(project, "Product")

    path, editable = generate_admin(project, "Product")

    assert editable is True
    source = path.read_text(encoding="utf-8")
    assert 'export const route = "/admin/products"' in source
    assert 'Schema<"ProductRead">' in source
    assert "api.patch(`/api/v1/products/${id}`" in source
    assert "startEdit" in source
    assert "<Pencil />" in source


def test_generate_admin_falls_back_to_delete_only_when_endpoint_lacks_patch(tmp_path):
    project = make_project(tmp_path, "a4")
    generate_model(project, "Widget", parse_fields(["name:string"]))
    endpoint_path = project / "backend" / "app" / "endpoints" / "widgets.py"
    endpoint_path.write_text(
        "from app.models.widget import Widget, WidgetCreate, WidgetRead\n"
        "from genesis import db, router\n\n"
        'api = router("/widgets")\n\n\n'
        "@api.get('', response_model=list[WidgetRead])\n"
        "def list_widgets():\n"
        "    return list(Widget.select().dicts())\n\n\n"
        "@api.delete('/{widget_id}', status_code=204)\n"
        "def delete_widget(widget_id: int):\n"
        "    Widget.delete_by_id(widget_id)\n",
        encoding="utf-8",
    )

    path, editable = generate_admin(project, "Widget")
    source = path.read_text(encoding="utf-8")

    assert editable is False
    assert "startEdit" not in source
    assert "Pencil" not in source
    assert "api.patch" not in source
    assert "Inline edit is unavailable" in source
    assert "<Input" not in source
    assert '"Input"' not in source


def test_generate_admin_output_has_no_unused_input_import_when_not_editable(tmp_path):
    project = make_project(tmp_path, "a5")
    generate_model(project, "Widget", parse_fields(["name:string"]))
    endpoint_path = project / "backend" / "app" / "endpoints" / "widgets.py"
    endpoint_path.write_text(
        "from app.models.widget import Widget, WidgetRead\n"
        "from genesis import router\n\n"
        'api = router("/widgets")\n\n\n'
        "@api.get('', response_model=list[WidgetRead])\n"
        "def list_widgets():\n"
        "    return list(Widget.select().dicts())\n",
        encoding="utf-8",
    )

    path, _ = generate_admin(project, "Widget")
    source = path.read_text(encoding="utf-8")

    assert 'import { Input } from "@/components/ui/input"' not in source


def test_generate_admin_excludes_id_and_created_at_from_editable_columns(tmp_path):
    project = make_project(tmp_path, "a6")
    generate_model(project, "Product", parse_fields(["name:string"]))
    generate_endpoint(project, "Product")

    path, _ = generate_admin(project, "Product")
    source = path.read_text(encoding="utf-8")

    assert "draft.id" not in source
    assert "draft.created_at" not in source
    assert source.count("<TableHead>") == 2  # ID + name


def test_destroy_admin_deletes_the_file(tmp_path):
    project = make_project(tmp_path, "a7")
    generate_model(project, "Product", parse_fields(["name:string"]))
    generate_endpoint(project, "Product")
    path, _ = generate_admin(project, "Product")

    destroy_admin(project, "Product")

    assert not path.exists()


def test_destroy_test_missing_raises(tmp_path):
    project = make_project(tmp_path, "p12g")
    with pytest.raises(GenerateError, match="does not exist"):
        destroy_test(project, "Product")


def test_destroy_admin_missing_file_raises(tmp_path):
    project = make_project(tmp_path, "a8")
    with pytest.raises(GenerateError, match="does not exist"):
        destroy_admin(project, "Product")


def test_scaffold_writes_all_four_files_and_regenerates_docs(tmp_path):
    project = make_project(tmp_path, "p13")
    paths = generate_scaffold(project, "Product", parse_fields(["name:string"]))

    assert paths["model"].exists()
    assert paths["endpoint"].exists()
    assert paths["page"].exists()
    assert paths["test"].exists()

    ast.parse(paths["model"].read_text(encoding="utf-8"))
    ast.parse(paths["endpoint"].read_text(encoding="utf-8"))
    ast.parse(paths["test"].read_text(encoding="utf-8"))


def test_scaffold_model_and_endpoint_agree_on_class_name(tmp_path):
    project = make_project(tmp_path, "p14")
    paths = generate_scaffold(project, "BlogPost", parse_fields(["title:string"]))

    model_source = paths["model"].read_text(encoding="utf-8")
    endpoint_source = paths["endpoint"].read_text(encoding="utf-8")
    assert "class BlogPost(db.Model)" in model_source
    assert "from app.models.blog_post import BlogPost" in endpoint_source
    assert 'router("/blog_posts")' in endpoint_source


def test_destroy_model_deletes_the_file(tmp_path):
    project = make_project(tmp_path, "p15")
    path = generate_model(project, "Product", [])
    assert path.exists()

    destroyed = destroy_model(project, "Product")

    assert destroyed == path
    assert not path.exists()


def test_destroy_endpoint_deletes_the_file(tmp_path):
    project = make_project(tmp_path, "p16")
    generate_model(project, "Product", [])
    path = generate_endpoint(project, "Product")

    destroy_endpoint(project, "Product")

    assert not path.exists()


def test_destroy_page_deletes_the_file(tmp_path):
    project = make_project(tmp_path, "p17")
    path = generate_page(project, "Product", [])

    destroy_page(project, "Product")

    assert not path.exists()


def test_destroy_missing_file_raises(tmp_path):
    project = make_project(tmp_path, "p18")
    with pytest.raises(GenerateError, match="does not exist"):
        destroy_model(project, "Product")


def test_destroy_scaffold_removes_everything(tmp_path):
    project = make_project(tmp_path, "p19")
    paths = generate_scaffold(project, "Product", parse_fields(["name:string"]))

    destroy_scaffold(project, "Product")

    assert not paths["model"].exists()
    assert not paths["endpoint"].exists()
    assert not paths["page"].exists()
    assert not paths["test"].exists()


def test_destroy_scaffold_tolerates_partial_state(tmp_path):
    project = make_project(tmp_path, "p20")
    paths = generate_scaffold(project, "Product", [])
    destroy_page(project, "Product")  # simulate the page already being gone

    result = destroy_scaffold(project, "Product")

    assert set(result) == {"model", "endpoint", "test"}
    assert not paths["model"].exists()
    assert not paths["endpoint"].exists()


def test_destroy_scaffold_raises_when_nothing_exists(tmp_path):
    project = make_project(tmp_path, "p21")
    with pytest.raises(GenerateError, match="nothing to destroy"):
        destroy_scaffold(project, "Product")


def test_scaffold_then_destroy_scaffold_round_trips_clean(tmp_path):
    project = make_project(tmp_path, "p22")
    before = sorted(p.relative_to(project) for p in project.rglob("*") if p.is_file())

    generate_scaffold(project, "Product", parse_fields(["name:string", "price:float"]))
    destroy_scaffold(project, "Product")

    after = sorted(p.relative_to(project) for p in project.rglob("*") if p.is_file())
    assert before == after


def test_cli_destroy_scaffold_regenerates_docs(tmp_path):
    project = make_project(tmp_path, "p23")
    gen_args = argparse.Namespace(
        target=str(project), name="Product", fields=["name:string"], force=False
    )
    assert generate_scaffold_cmd(gen_args) == 0
    assert "`products`" in (project / "DATABASE.md").read_text(encoding="utf-8")

    destroy_args = argparse.Namespace(target=str(project), name="Product", force=True)
    assert destroy_scaffold_cmd(destroy_args) == 0
    assert "`products`" not in (project / "DATABASE.md").read_text(encoding="utf-8")


def test_generate_model_references_requires_target_first(tmp_path):
    project = make_project(tmp_path, "p24")
    with pytest.raises(GenerateError, match="generate model User"):
        generate_model(project, "Order", parse_fields(["user:references"]))


def test_generate_model_references_imports_and_uses_fk(tmp_path):
    project = make_project(tmp_path, "p25")
    generate_model(project, "User", parse_fields(["email:string"]))
    source = generate_model(project, "Order", parse_fields(["user:references"])).read_text(
        encoding="utf-8"
    )

    ast.parse(source)  # must still be valid Python
    assert "from app.models.user import User" in source
    assert "user = db.FK(User)" in source
    assert "user: int" in source  # Create/Read/Update all flatten the FK to its id


def test_generate_model_references_explicit_target(tmp_path):
    project = make_project(tmp_path, "p26")
    generate_model(project, "User", [])
    source = generate_model(
        project, "Order", parse_fields(["placed_by:references:User"])
    ).read_text(encoding="utf-8")

    assert "from app.models.user import User" in source
    assert "placed_by = db.FK(User)" in source


def test_scaffold_with_reference_field_produces_valid_python(tmp_path):
    project = make_project(tmp_path, "p27")
    generate_model(project, "User", parse_fields(["email:string"]))
    paths = generate_scaffold(project, "Order", parse_fields(["user:references", "total:float"]))

    ast.parse(paths["model"].read_text(encoding="utf-8"))
    ast.parse(paths["endpoint"].read_text(encoding="utf-8"))


def test_generate_page_reference_field_is_a_number_input(tmp_path):
    project = make_project(tmp_path, "p28")
    generate_model(project, "User", [])
    source = generate_page(project, "Order", parse_fields(["user:references"])).read_text(
        encoding="utf-8"
    )
    assert 'type="number"' in source
    assert "Number(form.user)" in source


def test_generate_task_produces_typed_function_stub(tmp_path):
    project = make_project(tmp_path, "t1", preset="saas")
    fields = parse_fields(["to:string", "subject:string"])
    path = generate_task(project, "send_email", fields)
    source = path.read_text(encoding="utf-8")

    ast.parse(source)
    assert "@task" in source
    assert "def send_email(to: str, subject: str) -> str:" in source
    assert 'raise NotImplementedError("send_email: fill in the logic")' in source


def test_generate_task_rejects_references_param(tmp_path):
    project = make_project(tmp_path, "t2", preset="saas")
    with pytest.raises(GenerateError, match="doesn't make sense"):
        generate_task(project, "send_email", parse_fields(["user:references"]))


def test_generate_task_requires_jobs_module(tmp_path):
    project = make_project(tmp_path, "t3", preset="api")
    with pytest.raises(GenerateError, match="genesis add jobs"):
        generate_task(project, "send_email", [])


def test_destroy_task_deletes_the_file(tmp_path):
    project = make_project(tmp_path, "t4", preset="saas")
    path = generate_task(project, "send_email", [])
    assert path.exists()

    destroy_task(project, "send_email")

    assert not path.exists()


def test_destroy_task_missing_raises(tmp_path):
    project = make_project(tmp_path, "t5", preset="saas")
    with pytest.raises(GenerateError, match="does not exist"):
        destroy_task(project, "send_email")


def test_generate_task_then_destroy_round_trips_clean(tmp_path):
    project = make_project(tmp_path, "t6", preset="saas")
    before = sorted(p.relative_to(project) for p in project.rglob("*") if p.is_file())

    generate_task(project, "send_email", parse_fields(["to:string"]))
    destroy_task(project, "send_email")

    after = sorted(p.relative_to(project) for p in project.rglob("*") if p.is_file())
    assert before == after


def test_promote_task_requires_jobs_module(tmp_path):
    project = make_project(tmp_path, "t7", preset="api")
    source = project / "backend" / "app" / "endpoints" / "scratch.py"
    source.write_text("def compute_total(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")
    with pytest.raises(GenerateError, match="genesis add jobs"):
        promote_task(project, "backend/app/endpoints/scratch.py:compute_total")


def test_promote_task_self_contained_function_extracts_cleanly(tmp_path):
    project = make_project(tmp_path, "t8", preset="saas")
    source = project / "backend" / "app" / "endpoints" / "scratch.py"
    source.write_text(
        "import time\n\n\ndef compute_total(a: int, b: int) -> int:\n"
        "    time.sleep(0)\n    return a + b\n",
        encoding="utf-8",
    )

    path, warnings = promote_task(project, "backend/app/endpoints/scratch.py:compute_total")
    content = path.read_text(encoding="utf-8")

    assert warnings == []
    assert path == project / "backend" / "app" / "tasks" / "compute_total.py"
    ast.parse(content)
    assert "@task" in content
    assert "from genesis import task" in content
    assert "import time" in content
    assert "def compute_total(a: int, b: int) -> int:" in content
    assert "return a + b" in content


def test_promote_task_warns_about_unresolved_module_scope_reference(tmp_path):
    project = make_project(tmp_path, "t9", preset="saas")
    source = project / "backend" / "app" / "endpoints" / "scratch.py"
    source.write_text(
        'API_KEY = "secret"\n\n\ndef send_alert(message: str) -> str:\n'
        '    return f"{API_KEY}: {message}"\n',
        encoding="utf-8",
    )

    path, warnings = promote_task(project, "backend/app/endpoints/scratch.py:send_alert")
    content = path.read_text(encoding="utf-8")

    ast.parse(content)
    assert "API_KEY" in content
    assert any("API_KEY" in warning for warning in warnings)


def test_promote_task_missing_function_raises(tmp_path):
    project = make_project(tmp_path, "t10", preset="saas")
    source = project / "backend" / "app" / "endpoints" / "scratch.py"
    source.write_text("def a():\n    pass\n", encoding="utf-8")

    with pytest.raises(GenerateError, match="no top-level function 'b'"):
        promote_task(project, "backend/app/endpoints/scratch.py:b")
