from datetime import datetime

from peewee import (
    BooleanField,
    CharField,
    DateTimeField,
    FloatField,
    ForeignKeyField,
    IntegerField,
    TextField,
)
from playhouse.shortcuts import model_to_dict

from genesis.core.database import BaseModel as Model

Text = TextField
Char = CharField
Int = IntegerField
Float = FloatField
Bool = BooleanField
DateTime = DateTimeField
FK = ForeignKeyField
now = datetime.now


def to_dict(obj):
    return model_to_dict(obj, recurse=False)


__all__ = ["Model", "Text", "Char", "Int", "Float", "Bool", "DateTime", "FK", "now", "to_dict"]
