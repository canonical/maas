# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Configuration abstractions for the MAAS CLI."""


from contextlib import closing, contextmanager
import json
import os
from os.path import expanduser
import sqlite3


class ProfileConfig:
    """Store profile configurations in an sqlite3 database."""

    def __init__(self, database):
        self.database = database
        self.cache = {}
        with self.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS profiles "
                "(id INTEGER PRIMARY KEY,"
                " name TEXT NOT NULL UNIQUE,"
                " data BLOB)"
            )
        self.__fill_cache()

    def cursor(self):
        return closing(self.database.cursor())

    def __fill_cache(self):
        """Touch each entry in the database to fill the cache. This cache is
        needed to enforce a consistent view. Without it, the list of items can
        be out of sync with the items actually in the database leading to
        KeyErrors when traversing the profiles.
        """
        for name in self:
            try:
                self[name]
            except KeyError:
                pass

    def __iter__(self):
        if self.cache:
            return (name for name in self.cache)
        with self.cursor() as cursor:
            results = cursor.execute("SELECT name FROM profiles").fetchall()
        return (name for (name,) in results)

    def __getitem__(self, name):
        if name in self.cache:
            return self.cache[name]
        with self.cursor() as cursor:
            data = cursor.execute(
                "SELECT data FROM profiles" " WHERE name = ?", (name,)
            ).fetchone()
        if data is None:
            raise KeyError(name)
        else:
            info = json.loads(data[0])
            self.cache[name] = info
            return info

    def __setitem__(self, name, data):
        with self.cursor() as cursor:
            cursor.execute(
                "INSERT OR REPLACE INTO profiles (name, data) "
                "VALUES (?, ?)",
                (name, json.dumps(data)),
            )
        self.cache[name] = data

    def __delitem__(self, name):
        with self.cursor() as cursor:
            cursor.execute("DELETE FROM profiles" " WHERE name = ?", (name,))
        try:
            del self.cache[name]
        except KeyError:
            pass

    @classmethod
    def create_database(cls, dbpath):
        # Initialise the database file with restrictive permissions.
        os.close(os.open(dbpath, os.O_CREAT | os.O_APPEND, 0o600))

    @classmethod
    @contextmanager
    def open(cls, dbpath=expanduser("~/.maascli.db"), create=False):
        """Load a profiles database.

        Called without arguments this will open (and create, if create=True) a
        database in the user's home directory.

        **Note** that this returns a context manager which will close the
        database on exit, saving if the exit is clean.

        """
        if create:
            cls.create_database(dbpath)
        elif not os.path.exists(dbpath):
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
