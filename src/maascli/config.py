# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Configuration abstractions for the MAAS CLI."""

from contextlib import closing, contextmanager
import json
from pathlib import Path
import sqlite3


class ProfileConfig:
    """Store profile configurations in an sqlite3 database."""

    def __init__(self, database):
        self.database = database
        with self.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS profiles (
                  id INTEGER PRIMARY KEY,
                  name TEXT NOT NULL UNIQUE,
                  data BLOB
                )
                """
            )
        self.cache = self._profiles_cache()

    def cursor(self):
        return closing(self.database.cursor())

    def _profiles_cache(self):
        """Prefill cache with each profile in the database.

        This cache is needed to enforce a consistent view. Without it, the list
        of items can be out of sync with the items actually in the database
        leading to KeyErrors when traversing the profiles.
        """
        with self.cursor() as cursor:
            query = cursor.execute("SELECT name, data FROM profiles")
            return {name: json.loads(data) for name, data in query.fetchall()}

    def __iter__(self):
        return iter(self.cache)

    def __getitem__(self, name):
        return self.cache[name]

    def __setitem__(self, name, data):
        with self.cursor() as cursor:
            cursor.execute(
                "INSERT OR REPLACE INTO profiles (name, data) VALUES (?, ?)",
                (name, json.dumps(data)),
            )
        self.cache[name] = data

    def __delitem__(self, name):
        with self.cursor() as cursor:
            cursor.execute("DELETE FROM profiles WHERE name = ?", (name,))
        self.cache.pop(name, None)

    @classmethod
    def create_database(cls, dbpath):
        # Initialise the database file with restrictive permissions.
        Path(dbpath).touch(mode=0o600)

    @classmethod
    @contextmanager
    def open(cls, dbpath="~/.maascli.db", create=False):
        """Load a profiles database.

        Called without arguments this will open (and create, if create=True) a
        database in the user's home directory.

        **Note** that this returns a context manager which will close the
        database on exit, saving if the exit is clean.

        """
        dbpath = Path(dbpath).expanduser()
        if create:
            cls.create_database(dbpath)
        elif not dbpath.exists():
            raise FileNotFoundError(dbpath)
        database = sqlite3.connect(dbpath)
        try:
            yield cls(database)
        except BaseException:
            raise
        else:
            database.commit()
        finally:
            database.close()
