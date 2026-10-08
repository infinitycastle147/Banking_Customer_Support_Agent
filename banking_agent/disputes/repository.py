import sqlite3
from contextlib import contextmanager
from pathlib import Path


class DisputeStore:
    def __init__(self, path: Path):
        self.path = path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def transaction(self):
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        migrations = Path(__file__).resolve().parents[2] / "migrations"
        connection = self.connect()
        try:
            for schema in sorted(migrations.glob("*.sql")):
                connection.executescript(schema.read_text(encoding="utf-8"))
        finally:
            connection.close()
