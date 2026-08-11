#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for maasservicelayer.db (DatabaseConfig SSL / mTLS support)."""

import pytest

from maasservicelayer.db import (
    build_database_config,
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
        assert "sslmode" not in (url.query or {})

    def test_sslmode_verify_full_in_query(self) -> None:
        cfg = DatabaseConfig(
            name="maas", host="localhost", sslmode="verify-full"
        )
        url = cfg.dsn
        assert url.query.get("sslmode") == "verify-full"

    def test_ssl_cert_key_rootcert_in_query(self) -> None:
        cfg = DatabaseConfig(
            name="maas",
            host="localhost",
            sslmode="verify-full",
            sslcert="/etc/maas/db.crt",
            sslkey="/etc/maas/db.key",
            sslrootcert="/etc/maas/ca.crt",
        )
        url = cfg.dsn
        assert url.query.get("sslcert") == "/etc/maas/db.crt"
        assert url.query.get("sslkey") == "/etc/maas/db.key"
        assert url.query.get("sslrootcert") == "/etc/maas/ca.crt"

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
