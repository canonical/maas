# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `dbupgrade` management command."""

import pytest
from django.core.management import call_command

from maasservicelayer import db as db_module
from maasserver.management.commands.dbupgrade import Command
from maasserver.testing.testcase import MAASTransactionServerTestCase


class FakeSSLContext:
    def __init__(self, protocol) -> None:
        self.protocol = protocol
        self.check_hostname = None
        self.verify_mode = None
        self.verify_locations = []
        self.cert_chains = []

    def load_verify_locations(self, cafile) -> None:
        self.verify_locations.append(cafile)

    def load_cert_chain(self, certfile, keyfile=None) -> None:
        self.cert_chains.append((certfile, keyfile))


class TestDBUpgradeAlembicConfig:
    def test_build_alembic_postgres_dsn_omits_ssl_params(self):
        dsn = Command._build_alembic_postgres_dsn(
            {
                "dbname": "maasdb",
                "host": "db.example.com",
                "port": "5432",
                "user": "maas",
                "password": "secret",
                "sslmode": "verify-full",
                "sslcert": "/etc/maas/db.crt",
                "sslkey": "/etc/maas/db.key",
                "sslrootcert": "/etc/maas/ca.crt",
            }
        )

        assert (
            dsn
            == "postgresql+asyncpg://maas:secret@db.example.com:5432/maasdb"
        )

    @pytest.mark.parametrize(
        ("sslmode", "expected"),
        (("prefer", None), ("disable", False), ("allow", "allow")),
    )
    def test_build_alembic_connect_args_for_non_context_modes(
        self, sslmode, expected
    ):
        connect_args = Command._build_alembic_connect_args(
            {"dbname": "maasdb", "sslmode": sslmode}
        )

        assert connect_args == {"ssl": expected}

    def test_build_alembic_connect_args_builds_ssl_context(
        self, monkeypatch
    ):
        monkeypatch.setattr(db_module.ssl, "SSLContext", FakeSSLContext)

        connect_args = Command._build_alembic_connect_args(
            {
                "dbname": "maasdb",
                "host": "db.example.com",
                "port": "5432",
                "user": "maas",
                "password": "secret",
                "sslmode": "verify-full",
                "sslcert": "/etc/maas/db.crt",
                "sslkey": "/etc/maas/db.key",
                "sslrootcert": "/etc/maas/ca.crt",
            }
        )

        context = connect_args["ssl"]
        assert context.verify_mode == db_module.ssl.CERT_REQUIRED
        assert context.check_hostname is True
        assert context.verify_locations == ["/etc/maas/ca.crt"]
        assert context.cert_chains == [
            ("/etc/maas/db.crt", "/etc/maas/db.key")
        ]


class TestDBUpgrade(MAASTransactionServerTestCase):
    def test_dbupgrade(self):
        # Test is this doesn't fail.
        call_command("dbupgrade")
