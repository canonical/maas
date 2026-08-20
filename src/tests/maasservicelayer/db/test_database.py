#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for maasservicelayer.db (DatabaseConfig SSL / mTLS support)."""

import pytest

from maasservicelayer import db as db_module
from maasservicelayer.db import (
    build_database_config,
    Database,
    DatabaseConfig,
    InsecureDBSSLModeError,
)


class TestDatabaseConfigDsn:
    def test_no_ssl_params_no_query_string(self) -> None:
        cfg = DatabaseConfig(name="maas", host="localhost")
        url = cfg.dsn
        assert url.drivername == "postgresql+asyncpg"
        assert url.database == "maas"
        assert not url.query

    def test_sslmode_prefer_not_added_to_query(self) -> None:
        cfg = DatabaseConfig(name="maas", host="localhost", sslmode="prefer")
        url = cfg.dsn
        assert "ssl" not in (url.query or {})

    def test_sslmode_verify_full_in_query(self) -> None:
        cfg = DatabaseConfig(
            name="maas", host="localhost", sslmode="verify-full"
        )
        url = cfg.dsn
        assert not url.query

    @pytest.mark.parametrize(
        "sslmode", ["disable", "allow", "require", "verify-ca", "verify-full"]
    )
    def test_non_prefer_sslmode_not_in_query(self, sslmode) -> None:
        cfg = DatabaseConfig(name="maas", host="localhost", sslmode=sslmode)
        url = cfg.dsn
        assert not url.query

    def test_ssl_cert_key_rootcert_not_in_query(self) -> None:
        cfg = DatabaseConfig(
            name="maas",
            host="localhost",
            sslmode="verify-full",
            sslcert="/etc/maas/db.crt",
            sslkey="/etc/maas/db.key",
            sslrootcert="/etc/maas/ca.crt",
        )
        url = cfg.dsn
        assert not url.query

    def test_empty_ssl_paths_not_in_query(self) -> None:
        cfg = DatabaseConfig(
            name="maas",
            host="localhost",
            sslmode="verify-full",
        )
        url = cfg.dsn
        assert "sslcert" not in (url.query or {})
        assert "sslkey" not in (url.query or {})
        assert "sslrootcert" not in (url.query or {})


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


class TestDatabaseConfigBuildSSLParam:
    @pytest.fixture(autouse=True)
    def patch_ssl_context(self, monkeypatch) -> None:
        monkeypatch.setattr(db_module.ssl, "SSLContext", FakeSSLContext)

    def test_sslmode_prefer_uses_asyncpg_default(self) -> None:
        cfg = DatabaseConfig(name="maas", host="localhost", sslmode="prefer")
        assert cfg.build_ssl_param() is None

    def test_sslmode_disable_disables_ssl(self) -> None:
        cfg = DatabaseConfig(name="maas", host="localhost", sslmode="disable")
        assert cfg.build_ssl_param() is False

    def test_sslmode_allow_passes_through(self) -> None:
        cfg = DatabaseConfig(name="maas", host="localhost", sslmode="allow")
        assert cfg.build_ssl_param() == "allow"

    def test_sslmode_require_without_client_cert_uses_unverified_context(
        self,
    ) -> None:
        cfg = DatabaseConfig(name="maas", host="localhost", sslmode="require")
        context = cfg.build_ssl_param()
        assert context.verify_mode == db_module.ssl.CERT_NONE
        assert context.check_hostname is False
        assert context.cert_chains == []
        assert context.verify_locations == []

    def test_sslmode_require_with_client_cert_uses_unverified_context(
        self,
    ) -> None:
        cfg = DatabaseConfig(
            name="maas",
            host="localhost",
            sslmode="require",
            sslcert="/etc/maas/db.crt",
            sslkey="/etc/maas/db.key",
            sslrootcert="/etc/maas/ca.crt",
        )
        context = cfg.build_ssl_param()
        assert context.verify_mode == db_module.ssl.CERT_NONE
        assert context.check_hostname is False
        assert context.cert_chains == [
            ("/etc/maas/db.crt", "/etc/maas/db.key")
        ]
        assert context.verify_locations == []

    def test_sslmode_verify_ca_loads_ca_and_client_cert_without_hostname_check(
        self,
    ) -> None:
        cfg = DatabaseConfig(
            name="maas",
            host="localhost",
            sslmode="verify-ca",
            sslcert="/etc/maas/db.crt",
            sslkey="/etc/maas/db.key",
            sslrootcert="/etc/maas/ca.crt",
        )
        context = cfg.build_ssl_param()
        assert context.verify_mode == db_module.ssl.CERT_REQUIRED
        assert context.check_hostname is False
        assert context.verify_locations == ["/etc/maas/ca.crt"]
        assert context.cert_chains == [
            ("/etc/maas/db.crt", "/etc/maas/db.key")
        ]

    def test_sslmode_verify_full_loads_ca_and_client_cert_with_hostname_check(
        self,
    ) -> None:
        cfg = DatabaseConfig(
            name="maas",
            host="localhost",
            sslmode="verify-full",
            sslcert="/etc/maas/db.crt",
            sslkey="/etc/maas/db.key",
            sslrootcert="/etc/maas/ca.crt",
        )
        context = cfg.build_ssl_param()
        assert context.verify_mode == db_module.ssl.CERT_REQUIRED
        assert context.check_hostname is True
        assert context.verify_locations == ["/etc/maas/ca.crt"]
        assert context.cert_chains == [
            ("/etc/maas/db.crt", "/etc/maas/db.key")
        ]


class TestDatabase:
    def test_engine_uses_ssl_connect_arg(self, monkeypatch) -> None:
        calls = []

        def fake_create_async_engine(*args, **kwargs):
            calls.append((args, kwargs))
            return object()

        monkeypatch.setattr(
            db_module, "create_async_engine", fake_create_async_engine
        )
        cfg = DatabaseConfig(name="maas", host="localhost", sslmode="allow")

        Database(cfg)

        assert calls[0][1]["connect_args"] == {"ssl": "allow"}


class TestBuildDatabaseConfig:
    def test_non_hardening_allows_prefer(self) -> None:
        cfg = build_database_config(
            name="maas",
            host="localhost",
            sslmode="prefer",
            hardening_active=False,
        )
        assert cfg.sslmode == "prefer"

    @pytest.mark.parametrize(
        "sslmode", ["prefer", "disable", "allow", "require"]
    )
    def test_hardening_rejects_insecure_modes(self, sslmode) -> None:
        with pytest.raises(InsecureDBSSLModeError, match=sslmode):
            build_database_config(
                name="maas",
                host="localhost",
                sslmode=sslmode,
                hardening_active=True,
            )

    @pytest.mark.parametrize("sslmode", ["verify-full", "verify-ca"])
    def test_hardening_allows_verify_modes(self, sslmode) -> None:
        cfg = build_database_config(
            name="maas",
            host="localhost",
            sslmode=sslmode,
            hardening_active=True,
        )
        assert cfg.sslmode == sslmode

    def test_all_ssl_fields_forwarded(self) -> None:
        cfg = build_database_config(
            name="maas",
            host="db.local",
            username="maasuser",
            port=5432,
            sslmode="verify-full",
            sslcert="/etc/maas/db.crt",
            sslkey="/etc/maas/db.key",
            sslrootcert="/etc/maas/ca.crt",
            hardening_active=True,
        )
        assert cfg.sslcert == "/etc/maas/db.crt"
        assert cfg.sslkey == "/etc/maas/db.key"
        assert cfg.sslrootcert == "/etc/maas/ca.crt"
        assert cfg.username == "maasuser"
        assert cfg.port == 5432
