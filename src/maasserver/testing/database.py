# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS database cluster fixture."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "MAASClusterFixture",
    ]

from django.db import (
    connections,
    DEFAULT_DB_ALIAS,
    )
from postgresfixture import ClusterFixture


class MAASClusterFixture(ClusterFixture):

    def __init__(self, database=None):
        """
        @param database: The name of the database to use. Must correspond to a
            database defined in `django.db.connections`. If ``None``, then
            `DEFAULT_DB_ALIAS` is used.
        """
        self.connection = connections[
            DEFAULT_DB_ALIAS if database is None else database]
        super(MAASClusterFixture, self).__init__(
            datadir=self.connection.settings_dict["HOST"],
            preserve=True)

    @property
    def dbname(self):
        return self.connection.settings_dict["NAME"]

    def setUp(self):
        super(MAASClusterFixture, self).setUp()
        self.createdb(self.dbname)
