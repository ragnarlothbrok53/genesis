import peewee

from genesis import db as genesis_db


def test_to_dict_flattens_foreign_keys_to_their_id():
    sqlite = peewee.SqliteDatabase(":memory:")

    class Author(peewee.Model):
        name = peewee.CharField()

        class Meta:
            database = sqlite

    class Book(peewee.Model):
        title = peewee.CharField()
        author = peewee.ForeignKeyField(Author)

        class Meta:
            database = sqlite

    sqlite.create_tables([Author, Book])
    author = Author.create(name="Ada")
    book = Book.create(title="Genesis", author=author)

    assert genesis_db.to_dict(book) == {"id": book.id, "title": "Genesis", "author": author.id}
