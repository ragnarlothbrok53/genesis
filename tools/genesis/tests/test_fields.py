import pytest

from genesis_cli.fields import FieldError, parse_field, parse_fields, peewee_field, python_type


def test_parses_required_field():
    field = parse_field("name:string")
    assert field.name == "name"
    assert field.kind == "string"
    assert field.nullable is False


def test_parses_nullable_field():
    field = parse_field("description:text?")
    assert field.kind == "text"
    assert field.nullable is True


def test_rejects_missing_colon():
    with pytest.raises(FieldError, match="name:type"):
        parse_field("name")


def test_rejects_unknown_type():
    with pytest.raises(FieldError, match="unknown type"):
        parse_field("name:widget")


def test_rejects_invalid_identifier():
    with pytest.raises(FieldError, match="not a valid field name"):
        parse_field("2bad:string")


def test_rejects_reserved_names():
    with pytest.raises(FieldError, match="reserved"):
        parse_field("id:int")
    with pytest.raises(FieldError, match="reserved"):
        parse_field("created_at:datetime")


def test_parse_fields_parses_a_list():
    fields = parse_fields(["name:string", "price:float", "notes:text?"])
    assert [f.name for f in fields] == ["name", "price", "notes"]


def test_peewee_field_string_has_max_length():
    field = parse_field("name:string")
    assert peewee_field(field) == "db.Char(max_length=200)"


def test_peewee_field_nullable_string():
    field = parse_field("name:string?")
    assert peewee_field(field) == "db.Char(max_length=200, null=True)"


def test_peewee_field_non_nullable_bare_type():
    field = parse_field("price:float")
    assert peewee_field(field) == "db.Float()"


def test_peewee_field_nullable_bare_type():
    field = parse_field("price:float?")
    assert peewee_field(field) == "db.Float(null=True)"


def test_python_type_maps_kind():
    assert python_type(parse_field("age:int")) == "int"
    assert python_type(parse_field("age:int?")) == "int | None"


def test_python_type_force_optional_for_update_shapes():
    assert python_type(parse_field("age:int"), force_optional=True) == "int | None"


def test_references_infers_target_from_field_name():
    field = parse_field("user:references")
    assert field.kind == "references"
    assert field.target == "User"
    assert field.nullable is False


def test_references_accepts_explicit_target():
    field = parse_field("author:references:User")
    assert field.target == "User"


def test_references_nullable():
    field = parse_field("user:references?")
    assert field.nullable is True
    assert field.target == "User"


def test_references_explicit_target_nullable():
    field = parse_field("author:references:User?")
    assert field.nullable is True
    assert field.target == "User"


def test_references_rejects_too_many_segments():
    with pytest.raises(FieldError, match="at most one target"):
        parse_field("user:references:User:Extra")


def test_non_references_type_rejects_extra_segments():
    with pytest.raises(FieldError, match="only 'references'"):
        parse_field("name:string:extra")


def test_peewee_field_references():
    field = parse_field("user:references")
    assert peewee_field(field) == "db.FK(User)"


def test_peewee_field_references_nullable():
    field = parse_field("user:references?")
    assert peewee_field(field) == "db.FK(User, null=True)"


def test_python_type_references_is_int():
    assert python_type(parse_field("user:references")) == "int"
    assert python_type(parse_field("user:references?")) == "int | None"
