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
    databases: dict,
    monkeypatch,
    sslcert="",
    sslkey="",
    sslrootcert="",
    temporal_bind="",
    broadcast_address="10.0.0.1",
    hardening_active=False,
    source_address_for_url="10.0.0.1",
):
    """
    Run RegionTemporalService._configure() with patched dependencies.

    Returns a 2-tuple of the environ dict captured from the first
    template.substitute() call, and the number of times
    `get_source_address_for_url` was called via temporal.py's own alias
    (the broadcast-address fallback), separate from any calls made
    internally by `resolve_bind_address` (see the note below).
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
            "maasserver.regiondservices.temporal.get_source_address_for_url",
            return_value=source_address_for_url,
        ) as mock_get_source_address,
        # `resolve_bind_address` (called by `_configure`) looks up
        # `get_source_address_for_url` in its own defining module, not
        # via temporal.py's imported alias above, so it needs its own patch.
        mock.patch(
            "provisioningserver.utils.network.get_source_address_for_url",
            return_value=source_address_for_url,
        ),
        mock.patch(
            "maasserver.regiondservices.temporal._hardening.is_hardening_enabled",
            return_value=hardening_active,
        ),
        mock.patch(
            "maasserver.regiondservices.temporal.load_template",
            side_effect=[tpl, FakeTemplate()],
        ),
    ):
        mock_settings.DATABASES = databases
        mock_conn._alias = "default"
        ctx = mock_cfg.open.return_value.__enter__.return_value
        ctx.broadcast_address = broadcast_address
        ctx.maas_url = "http://maas"
        ctx.temporal_bind = temporal_bind
        ctx.database_sslcert = sslcert
        ctx.database_sslkey = sslkey
        ctx.database_sslrootcert = sslrootcert

        svc = RegionTemporalService()
        svc._configure()

    return tpl.environs[0], mock_get_source_address.call_count


@pytest.mark.parametrize("sslmode", ["prefer", "allow", "disable"])
def test_tls_disabled_for_non_encrypting_modes(sslmode, tmp_path, monkeypatch):
    monkeypatch.setenv("MAAS_TEMPORAL_CONFIG_DIR", str(tmp_path))
    environ, _ = _run_configure(_db_with_sslmode(sslmode), monkeypatch)
    assert environ["tls_enabled"] == "false"
    assert environ["enable_host_verification"] == "false"


def test_tls_enabled_no_host_verif_for_require(tmp_path, monkeypatch):
    monkeypatch.setenv("MAAS_TEMPORAL_CONFIG_DIR", str(tmp_path))
    environ, _ = _run_configure(_db_with_sslmode("require"), monkeypatch)
    assert environ["tls_enabled"] == "true"
    assert environ["enable_host_verification"] == "false"


@pytest.mark.parametrize("sslmode", ["verify-ca", "verify-full"])
def test_tls_enabled_with_host_verif_for_verify_modes(
    sslmode, tmp_path, monkeypatch
):
    monkeypatch.setenv("MAAS_TEMPORAL_CONFIG_DIR", str(tmp_path))
    environ, _ = _run_configure(_db_with_sslmode(sslmode), monkeypatch)
    assert environ["tls_enabled"] == "true"
    assert environ["enable_host_verification"] == "true"


def test_tls_disabled_when_options_has_no_sslmode(tmp_path, monkeypatch):
    """Missing sslmode in OPTIONS defaults to prefer → TLS off."""
    monkeypatch.setenv("MAAS_TEMPORAL_CONFIG_DIR", str(tmp_path))
    db = {k: dict(v) for k, v in _BASE_DATABASES.items()}
    db["default"]["OPTIONS"] = {}
    environ, _ = _run_configure(db, monkeypatch)
    assert environ["tls_enabled"] == "false"


def test_tls_disabled_when_databases_has_no_options(tmp_path, monkeypatch):
    """Missing OPTIONS key entirely defaults to prefer → TLS off."""
    monkeypatch.setenv("MAAS_TEMPORAL_CONFIG_DIR", str(tmp_path))
    db = {k: dict(v) for k, v in _BASE_DATABASES.items()}
    del db["default"]["OPTIONS"]
    environ, _ = _run_configure(db, monkeypatch)
    assert environ["tls_enabled"] == "false"


def test_cert_fields_forwarded_when_present(tmp_path, monkeypatch):
    """Client cert paths are passed through to the template environ."""
    monkeypatch.setenv("MAAS_TEMPORAL_CONFIG_DIR", str(tmp_path))
    environ, _ = _run_configure(
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
    environ, _ = _run_configure(_db_with_sslmode("require"), monkeypatch)
    assert environ["database_sslcert"] == ""
    assert environ["database_sslkey"] == ""
    assert environ["database_sslrootcert"] == ""


def test_client_cert_without_ca_forwarded(tmp_path, monkeypatch):
    """Client cert without a custom CA is valid (system CA chain is used)."""
    monkeypatch.setenv("MAAS_TEMPORAL_CONFIG_DIR", str(tmp_path))
    environ, _ = _run_configure(
        _db_with_sslmode("verify-full"),
        monkeypatch,
        sslcert="/etc/maas/db.crt",
        sslkey="/etc/maas/db.key",
    )
    assert environ["database_sslcert"] == "/etc/maas/db.crt"
    assert environ["database_sslkey"] == "/etc/maas/db.key"
    assert environ["database_sslrootcert"] == ""


def test_broadcast_address_matches_explicit_temporal_bind(
    tmp_path, monkeypatch
):
    """An explicit, non-wildcard temporal_bind (e.g. loopback on an
    all-in-one host) is used as the broadcast address, not a value
    independently derived from maas_url."""
    monkeypatch.setenv("MAAS_TEMPORAL_CONFIG_DIR", str(tmp_path))
    environ, get_source_address_calls = _run_configure(
        _BASE_DATABASES,
        monkeypatch,
        temporal_bind="127.0.0.1",
        broadcast_address="",
        source_address_for_url="10.0.0.5",
    )
    assert environ["temporal_bind"] == "127.0.0.1"
    assert environ["broadcast_address"] == "127.0.0.1"
    # maas_url was never consulted for the broadcast address.
    assert get_source_address_calls == 0


def test_broadcast_address_explicit_value_wins(tmp_path, monkeypatch):
    """An explicitly configured broadcast_address always takes
    precedence, even if it disagrees with temporal_bind."""
    monkeypatch.setenv("MAAS_TEMPORAL_CONFIG_DIR", str(tmp_path))
    environ, _ = _run_configure(
        _BASE_DATABASES,
        monkeypatch,
        temporal_bind="127.0.0.1",
        broadcast_address="192.168.1.1",
    )
    assert environ["broadcast_address"] == "192.168.1.1"


def test_broadcast_address_matches_derived_temporal_bind(
    tmp_path, monkeypatch
):
    """When temporal_bind is itself derived from maas_url, the broadcast
    address agrees with it (no regression for the non-hardened default)."""
    monkeypatch.setenv("MAAS_TEMPORAL_CONFIG_DIR", str(tmp_path))
    environ, _ = _run_configure(
        _BASE_DATABASES,
        monkeypatch,
        temporal_bind="",
        broadcast_address="",
        source_address_for_url="10.0.0.9",
    )
    assert environ["temporal_bind"] == "10.0.0.9"
    assert environ["broadcast_address"] == "10.0.0.9"


def test_broadcast_address_falls_back_when_temporal_bind_is_wildcard(
    tmp_path, monkeypatch
):
    """A wildcard bind isn't a dialable destination, so the broadcast
    address still falls back to a maas_url-derived address."""
    monkeypatch.setenv("MAAS_TEMPORAL_CONFIG_DIR", str(tmp_path))
    environ, get_source_address_calls = _run_configure(
        _BASE_DATABASES,
        monkeypatch,
        temporal_bind="",
        broadcast_address="",
        hardening_active=False,
        source_address_for_url=None,
    )
    assert environ["temporal_bind"] == "0.0.0.0"
    assert environ["broadcast_address"] is None
    # The broadcast-address fallback consults maas_url directly, on top
    # of resolve_bind_address's own internal (separately mocked) lookup.
    assert get_source_address_calls == 1
