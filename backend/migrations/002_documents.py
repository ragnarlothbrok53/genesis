import peewee as pw
from peewee_migrate import Migrator
from pgvector.peewee import VectorField

EMBEDDING_DIMENSIONS = 1536


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    migrator.sql("CREATE EXTENSION IF NOT EXISTS vector")

    @migrator.create_model
    class Document(pw.Model):
        id = pw.AutoField()
        content = pw.TextField()
        embedding = VectorField(dimensions=EMBEDDING_DIMENSIONS)
        created_at = pw.DateTimeField()

        class Meta:
            table_name = "documents"


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    migrator.remove_model("documents")
