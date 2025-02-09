# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""PostgresListener test helpers."""

from twisted.internet.defer import succeed

from maasserver.listener import PostgresListenerService


class FakePostgresListenerService(PostgresListenerService):
    "Fake PostgresListenerService that doesn't actually start."

    def startService():
        # So its not actually started.
        return succeed(None)

    def stopService():
        # So its not actually stopped.
        return succeed(None)
