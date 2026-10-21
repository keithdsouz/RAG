import importlib
import re
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from ..models import Document
from .base import Source

_READ_ONLY_SQL = re.compile(r'^\s*(select|with)\b', re.IGNORECASE)


class DatabaseSource(Source):
    """Index rows returned by a read-only SQL query.

    `url` is `sqlite:///path/to.db`, or any SQLAlchemy URL when SQLAlchemy and the driver are installed.
    Each row becomes one document made of `column: value` lines for `text_columns`.
    """

    type = 'database'

    def __init__(
        self,
        url: str,
        query: str,
        id_column: str,
        title_column: str | None = None,
        text_columns: list[str] | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__()
        if not _READ_ONLY_SQL.match(query):
            raise ValueError('Database source query must be a SELECT (or WITH ... SELECT) statement.')
        self.url = url
        self.query = query
        self.id_column = id_column
        self.title_column = title_column
        self.text_columns = text_columns
        self.name = name or 'database'

    @property
    def label(self) -> str:
        return self.name

    def documents(self) -> Iterator[Document]:
        for row in self._rows():
            if self.id_column not in row:
                raise KeyError(f'id_column "{self.id_column}" not in query result columns: {list(row)}')
            row_id = row[self.id_column]
            columns = self.text_columns or [column for column in row if column != self.id_column]
            text = '\n'.join(f'{column}: {row[column]}' for column in columns if row.get(column) not in (None, ''))
            if not text.strip():
                self.skipped += 1
                continue
            title = str(row.get(self.title_column) or row_id) if self.title_column else str(row_id)
            yield Document(
                doc_id=f'db:{self.name}:{row_id}',
                source_type=self.type,
                uri=f'db://{self.name}/{row_id}',
                title=title,
                text=text,
            )

    def _rows(self) -> Iterator[dict]:
        if self.url.startswith('sqlite:///'):
            yield from self._sqlite_rows(self.url[len('sqlite:///'):])
        else:
            yield from self._sqlalchemy_rows()

    def _sqlite_rows(self, db_path: str) -> Iterator[dict]:
        resolved = Path(db_path).expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(f'SQLite database not found: {resolved}')
        connection = sqlite3.connect(f'{resolved.as_uri()}?mode=ro', uri=True)
        connection.row_factory = sqlite3.Row
        try:
            for row in connection.execute(self.query):
                yield dict(row)
        finally:
            connection.close()

    def _sqlalchemy_rows(self) -> Iterator[dict]:
        try:
            sqlalchemy = importlib.import_module('sqlalchemy')
        except ImportError as error:
            raise RuntimeError(
                'Only sqlite:/// URLs work without extra packages. Install sqlalchemy (and a driver) for other databases.'
            ) from error

        engine = sqlalchemy.create_engine(self.url)
        try:
            with engine.connect() as connection:
                for row in connection.execute(sqlalchemy.text(self.query)).mappings():
                    yield dict(row)
        finally:
            engine.dispose()
