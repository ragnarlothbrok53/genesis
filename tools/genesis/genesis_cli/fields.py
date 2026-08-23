from dataclasses import dataclass

from genesis_cli.inflect import pascal_case

TYPES = {
    "string": "str",
    "text": "str",
    "int": "int",
    "integer": "int",
    "float": "float",
    "bool": "bool",
    "boolean": "bool",
    "datetime": "datetime",
}

_PEEWEE_CTOR = {
    "string": "db.Char",
    "text": "db.Text",
    "int": "db.Int",
    "integer": "db.Int",
    "float": "db.Float",
    "bool": "db.Bool",
    "boolean": "db.Bool",
    "datetime": "db.DateTime",
}


class FieldError(Exception):
    pass


@dataclass
class FieldSpec:
    name: str
    kind: str
    nullable: bool
    target: str | None = None  # PascalCase model name, only set when kind == "references"


def parse_field(raw: str) -> FieldSpec:
    if ":" not in raw:
        raise FieldError(
            f"'{raw}' is not name:type — e.g. name:string, description:text? or user:references"
        )
    name, rest = raw.split(":", 1)
    if not name.isidentifier():
        raise FieldError(f"'{name}' is not a valid field name")
    if name in ("id", "created_at"):
        raise FieldError(f"'{name}' is reserved — every model already has it")

    nullable = rest.endswith("?")
    rest = rest[:-1] if nullable else rest
    parts = rest.split(":")
    kind = parts[0]

    if kind == "references":
        if len(parts) > 2:
            raise FieldError(f"'{raw}' — references takes at most one target, e.g. user:references:Author")
        target = pascal_case(parts[1]) if len(parts) == 2 else pascal_case(name)
        return FieldSpec(name=name, kind=kind, nullable=nullable, target=target)

    if len(parts) > 1:
        raise FieldError(f"'{raw}' — only 'references' takes a target model")
    if kind not in TYPES:
        available = ", ".join([*sorted(TYPES), "references"])
        raise FieldError(f"unknown type '{kind}' in '{raw}'; available: {available}")
    return FieldSpec(name=name, kind=kind, nullable=nullable)


def parse_fields(raw_fields: list[str]) -> list[FieldSpec]:
    return [parse_field(raw) for raw in raw_fields]


def peewee_field(field: FieldSpec) -> str:
    if field.kind == "references":
        args = field.target + (", null=True" if field.nullable else "")
        return f"db.FK({args})"
    ctor = _PEEWEE_CTOR[field.kind]
    if field.kind == "string":
        args = "max_length=200" + (", null=True" if field.nullable else "")
        return f"{ctor}({args})"
    return f"{ctor}(null=True)" if field.nullable else f"{ctor}()"


def python_type(field: FieldSpec, force_optional: bool = False) -> str:
    base = "int" if field.kind == "references" else TYPES[field.kind]
    return f"{base} | None" if field.nullable or force_optional else base


def create_field(field: FieldSpec) -> str:
    if field.nullable:
        return f"{python_type(field)} = None"
    if field.kind == "string":
        return "str = Field(min_length=1, max_length=200)"
    return python_type(field)
