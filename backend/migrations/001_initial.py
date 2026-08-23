import peewee as pw
from peewee_migrate import Migrator


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    @migrator.create_model
    class Item(pw.Model):
        id = pw.AutoField()
        name = pw.CharField(max_length=200)
        description = pw.TextField(null=True)
        created_at = pw.DateTimeField()

        class Meta:
            table_name = "items"


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    migrator.remove_model("items")
