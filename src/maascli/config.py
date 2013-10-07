# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Configuration abstractions for the MAAS CLI."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "ProfileConfig",
    ]

from contextlib import (
    closing,
    contextmanager,
    )
import json
import os
from os.path import expanduser
import sqlite3


class ProfileConfig:
    """Store profile configurations in an sqlite3 database."""

    def __init__(self, database):
        self.database = database
        with self.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS profiles "
                "(id INTEGER PRIMARY KEY,"
                " name TEXT NOT NULL UNIQUE,"
                " data BLOB)")

    def cursor(self):
        return closing(self.database.cursor())

    def __iter__(self):
        with self.cursor() as cursor:
            results = cursor.execute(
                "SELECT name FROM profiles").fetchall()
        return (name for (name,) in results)

    def __getitem__(self, name):
        with self.cursor() as cursor:
            [data] = cursor.execute(
                "SELECT data FROM profiles"
                " WHERE name = ?", (name,)).fetchone()
        return json.loads(data)

    def __setitem__(self, name, data):
        with self.cursor() as cursor:
            cursor.execute(
                "INSERT OR REPLACE INTO profiles (name, data) "
                "VALUES (?, ?)", (name, json.dumps(data)))

    def __delitem__(self, name):
        with self.cursor() as cursor:
            cursor.execute(
                "DELETE FROM profiles"
                " WHERE name = ?", (name,))

    @classmethod
    @contextmanager
    def open(cls, dbpath=expanduser("~/.maascli.db")):
        """Load a profiles database.

        Called without arguments this will open (and create) a database in the
        user's home directory.

        **Note** that this returns a context manager which will close the
        database on exit, saving if the exit is clean.
        """
        # Initialise filename with restrictive permissions...
        os.close(os.open(dbpath, os.O_CREAT | os.O_APPEND, 0600))
        # before opening it with sqlite.
        database = sqlite3.connect(dbpath)
        try:
            yield cls(database)
        except:
            raise
        else:
            database.commit()
        finally:
            database.close()
