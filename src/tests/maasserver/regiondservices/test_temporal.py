#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for TLS configuration in RegionTemporalService._configure()."""

from unittest import mock

import pytest

from maasserver.regiondservices.temporal import RegionTemporalService

_BASE_DATABASES = {
    "default": {
        "NAME": "testdb",
        "USER": "testuser",
        "PASSWORD": "testpass",
        "HOST": "localhost",
        "PORT": "5432",
        "OPTIONS": {},
    }
}


def _db_with_sslmode(sslmode: str) -> dict:
    db = {k: dict(v) for k, v in _BASE_DATABASES.items()}
    db["default"]["OPTIONS"] = {"sslmode": sslmode}
    return db


class FakeTemplate:
    """Tempita stub that records the environ passed to substitute()."""

    def __init__(self):
        self.environs = []

    def substitute(self, environ):
        self.environs.append(dict(environ))
        return "rendered"


def _run_configure(
    databases: dict, monkeypatch, sslcert="", sslkey="", sslrootcert=""
):
    """
    Run RegionTemporalService._configure() with patched dependencies.

    Returns the environ dict captured from the first template.substitute call.
    """
    tpl = FakeTemplate()

    with (
        mock.patch(
            "maasserver.regiondservices.temporal.settings"
        ) as mock_settings,
        mock.patch(
            "maasserver.regiondservices.temporal.django_connection"
        ) as mock_conn,
        mock.patch(
            "maasserver.regiondservices.temporal.RegionConfiguration"
        ) as mock_cfg,
        mock.patch(
            "maasserver.regiondservices.temporal.get_maas_data_path",
            return_value="/tmp/temporal",
        ),
        mock.patch(
            "maasserver.regiondservices.temporal.get_maas_cluster_cert_paths",
            return_value=("cert.pem", "key.pem", "ca.pem"),
        ),
        mock.patch("maasserver.regiondservices.temporal.atomic_write"),
        mock.patch(
            "maasserver.regiondservices.temporal.load_template",
            side_effect=[tpl, FakeTemplate()],
        ),
    ):
        mock_settings.DATABASES = databases
        mock_conn._alias = "default"
        ctx = mock_cfg.open.return_value.__enter__.return_value
        ctx.broadcast_address = "10.0.0.1"
        ctx.maas_url = "http://maas"
        ctx.temporal_bind = ""
        ctx.database_sslcert = sslcert
        ctx.database_sslkey = sslkey
        ctx.database_sslrootcert = sslrootcert

        svc = RegionTemporalService()
        svc._configure()

    return tpl.environs[0]


@pytest.mark.parametrize("sslmode", ["prefer", "allow", "disable"])
def test_tls_disabled_for_non_encrypting_modes(sslmode, tmp_path, monkeypatch):
    monkeypatch.setenv("MAAS_TEMPORAL_CONFIG_DIR", str(tmp_path))
    environ = _run_configure(_db_with_sslmode(sslmode), monkeypatch)
    assert environ["tls_enabled"] is False
    assert environ["enable_host_verification"] is False


def test_tls_enabled_no_host_verif_for_require(tmp_path, monkeypatch):
    monkeypatch.setenv("MAAS_TEMPORAL_CONFIG_DIR", str(tmp_path))
    environ = _run_configure(_db_with_sslmode("require"), monkeypatch)
    assert environ["tls_enabled"] is True
    assert environ["enable_host_verification"] is False


@pytest.mark.parametrize("sslmode", ["verify-ca", "verify-full"])
def test_tls_enabled_with_host_verif_for_verify_modes(
    sslmode, tmp_path, monkeypatch
):
    monkeypatch.setenv("MAAS_TEMPORAL_CONFIG_DIR", str(tmp_path))
    environ = _run_configure(_db_with_sslmode(sslmode), monkeypatch)
    assert environ["tls_enabled"] is True
    assert environ["enable_host_verification"] is True


def test_tls_disabled_when_options_has_no_sslmode(tmp_path, monkeypatch):
    """Missing sslmode in OPTIONS defaults to prefer → TLS off."""
    monkeypatch.setenv("MAAS_TEMPORAL_CONFIG_DIR", str(tmp_path))
    db = {k: dict(v) for k, v in _BASE_DATABASES.items()}
    db["default"]["OPTIONS"] = {}
    environ = _run_configure(db, monkeypatch)
    assert environ["tls_enabled"] is False


def test_tls_disabled_when_databases_has_no_options(tmp_path, monkeypatch):
    """Missing OPTIONS key entirely defaults to prefer → TLS off."""
    monkeypatch.setenv("MAAS_TEMPORAL_CONFIG_DIR", str(tmp_path))
    db = {k: dict(v) for k, v in _BASE_DATABASES.items()}
    del db["default"]["OPTIONS"]
    environ = _run_configure(db, monkeypatch)
    assert environ["tls_enabled"] is False


def test_cert_fields_forwarded_when_present(tmp_path, monkeypatch):
    """Client cert paths are passed through to the template environ."""
    monkeypatch.setenv("MAAS_TEMPORAL_CONFIG_DIR", str(tmp_path))
    environ = _run_configure(
        _db_with_sslmode("verify-full"),
        monkeypatch,
        sslcert="/etc/maas/db.crt",
        sslkey="/etc/maas/db.key",
        sslrootcert="/etc/maas/ca.crt",
    )
    assert environ["database_sslcert"] == "/etc/maas/db.crt"
    assert environ["database_sslkey"] == "/etc/maas/db.key"
    assert environ["database_sslrootcert"] == "/etc/maas/ca.crt"


def test_cert_fields_empty_when_not_configured(tmp_path, monkeypatch):
    """Cert paths are empty strings when no client cert is configured."""
    monkeypatch.setenv("MAAS_TEMPORAL_CONFIG_DIR", str(tmp_path))
    environ = _run_configure(_db_with_sslmode("require"), monkeypatch)
    assert environ["database_sslcert"] == ""
    assert environ["database_sslkey"] == ""
    assert environ["database_sslrootcert"] == ""


def test_client_cert_without_ca_forwarded(tmp_path, monkeypatch):
    """Client cert without a custom CA is valid (system CA chain is used)."""
    monkeypatch.setenv("MAAS_TEMPORAL_CONFIG_DIR", str(tmp_path))
    environ = _run_configure(
        _db_with_sslmode("verify-full"),
        monkeypatch,
        sslcert="/etc/maas/db.crt",
        sslkey="/etc/maas/db.key",
    )
    assert environ["database_sslcert"] == "/etc/maas/db.crt"
    assert environ["database_sslkey"] == "/etc/maas/db.key"
    assert environ["database_sslrootcert"] == ""
