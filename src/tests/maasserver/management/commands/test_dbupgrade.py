#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for TLS handling in the dbupgrade management command."""

from unittest import mock

import pytest

from maasserver.management.commands.dbupgrade import Command


def _make_conn(sslmode: str):
    """Build a mock Django connection whose params include *sslmode*."""
    conn = mock.MagicMock()
    cursor = mock.MagicMock()
    # Two fetchone calls: temporal.schema_version, temporal_visibility.schema_version
    cursor.fetchone.side_effect = [[None], [None]]
    conn.cursor.return_value.__enter__.return_value = cursor
    conn.get_connection_params.return_value = {
        "host": "localhost",
        "port": "5432",
        "dbname": "testdb",
        "user": "testuser",
        "password": "testpass",
        "sslmode": sslmode,
    }
    return conn


def _make_conn_with_certs(sslmode, sslcert="", sslkey="", sslrootcert=""):
    conn = mock.MagicMock()
    cursor = mock.MagicMock()
    cursor.fetchone.side_effect = [[None], [None]]
    conn.cursor.return_value.__enter__.return_value = cursor
    conn.get_connection_params.return_value = {
        "host": "localhost",
        "port": "5432",
        "dbname": "testdb",
        "user": "testuser",
        "password": "testpass",
        "sslmode": sslmode,
        **({"sslcert": sslcert} if sslcert else {}),
        **({"sslkey": sslkey} if sslkey else {}),
        **({"sslrootcert": sslrootcert} if sslrootcert else {}),
    }
    return conn


def _tls_flags(mock_subprocess):
    """Return the first command list passed to check_output."""
    return mock_subprocess.call_args_list[0][0][0]


@pytest.fixture(autouse=True)
def patch_get_path():
    with mock.patch(
        "maasserver.management.commands.dbupgrade.get_path",
        side_effect=lambda x: x,
    ):
        yield


@pytest.fixture
def mock_subprocess():
    with mock.patch(
        "maasserver.management.commands.dbupgrade.subprocess.check_output"
    ) as m:
        yield m


@pytest.fixture
def mock_connections():
    with mock.patch(
        "maasserver.management.commands.dbupgrade.connections"
    ) as m:
        yield m


@pytest.mark.parametrize("sslmode", ["prefer", "allow", "disable"])
def test_temporal_migration_no_tls_for_non_encrypting_modes(
    mock_connections, mock_subprocess, sslmode
):
    mock_connections.__getitem__.return_value = _make_conn(sslmode)
    Command._temporal_migration("default")
    cmd = _tls_flags(mock_subprocess)
    assert "--tls" not in cmd
    assert "--tls-disable-host-verification" not in cmd


def test_temporal_migration_tls_plus_disable_host_verif_for_require(
    mock_connections, mock_subprocess
):
    mock_connections.__getitem__.return_value = _make_conn("require")
    Command._temporal_migration("default")
    cmd = _tls_flags(mock_subprocess)
    assert "--tls" in cmd
    assert "--tls-disable-host-verification" in cmd


@pytest.mark.parametrize("sslmode", ["verify-ca", "verify-full"])
def test_temporal_migration_tls_with_host_verif_for_verify_modes(
    mock_connections, mock_subprocess, sslmode
):
    mock_connections.__getitem__.return_value = _make_conn(sslmode)
    Command._temporal_migration("default")
    cmd = _tls_flags(mock_subprocess)
    assert "--tls" in cmd
    assert "--tls-disable-host-verification" not in cmd


def test_temporal_migration_passes_client_cert_flags(
    mock_connections, mock_subprocess
):
    conn = _make_conn_with_certs(
        "verify-full",
        sslcert="/etc/maas/db.crt",
        sslkey="/etc/maas/db.key",
        sslrootcert="/etc/maas/ca.crt",
    )
    mock_connections.__getitem__.return_value = conn
    Command._temporal_migration("default")
    cmd = _tls_flags(mock_subprocess)
    assert "--tls" in cmd
    assert "--tls-cert-file" in cmd
    assert cmd[cmd.index("--tls-cert-file") + 1] == "/etc/maas/db.crt"
    assert "--tls-key-file" in cmd
    assert cmd[cmd.index("--tls-key-file") + 1] == "/etc/maas/db.key"
    assert "--tls-ca-file" in cmd
    assert cmd[cmd.index("--tls-ca-file") + 1] == "/etc/maas/ca.crt"


def test_temporal_migration_no_ca_file_without_client_cert(
    mock_connections, mock_subprocess
):
    """sslrootcert without a client cert must not produce --tls-ca-file."""
    conn = _make_conn_with_certs("verify-ca", sslrootcert="/etc/maas/ca.crt")
    mock_connections.__getitem__.return_value = conn
    Command._temporal_migration("default")
    cmd = _tls_flags(mock_subprocess)
    assert "--tls" in cmd
    assert "--tls-ca-file" not in cmd
    assert "--tls-cert-file" not in cmd


def test_temporal_migration_no_cert_flags_when_certs_absent(
    mock_connections, mock_subprocess
):
    conn = _make_conn_with_certs("require")  # TLS on, no certs
    mock_connections.__getitem__.return_value = conn
    Command._temporal_migration("default")
    cmd = _tls_flags(mock_subprocess)
    assert "--tls" in cmd
    assert "--tls-cert-file" not in cmd
    assert "--tls-ca-file" not in cmd


@pytest.mark.parametrize("sslmode", ["require", "verify-full"])
def test_build_alembic_postgres_dsn_sslmode_propagated_verbatim(sslmode):
    params = {
        "host": "dbhost.example.com",
        "port": "5432",
        "dbname": "testdb",
        "user": "testuser",
        "password": "testpass",
        "sslmode": sslmode,
    }
    dsn = Command._build_alembic_postgres_dsn(params)
    assert f"ssl={sslmode}" in dsn


def test_build_alembic_postgres_dsn_tcp_defaults_ssl_to_prefer():
    params = {
        "host": "dbhost.example.com",
        "port": "5432",
        "dbname": "testdb",
        "user": "testuser",
        "password": "testpass",
        # no sslmode key
    }
    dsn = Command._build_alembic_postgres_dsn(params)
    assert "ssl=prefer" in dsn


def test_build_alembic_postgres_dsn_unix_socket_excludes_ssl_param():
    params = {
        "host": "/var/run/postgresql",
        "port": "5432",
        "dbname": "testdb",
        "user": "testuser",
        "password": "testpass",
        "sslmode": "require",
    }
    dsn = Command._build_alembic_postgres_dsn(params)
    assert "ssl=" not in dsn
    assert "host=/var/run/postgresql" in dsn


def test_build_alembic_postgres_dsn_includes_cert_params():
    params = {
        "host": "pg.internal",
        "port": "5432",
        "dbname": "maasdb",
        "user": "maas",
        "password": "",
        "sslmode": "verify-full",
        "sslcert": "/etc/maas/db.crt",
        "sslkey": "/etc/maas/db.key",
        "sslrootcert": "/etc/maas/ca.crt",
    }
    dsn = Command._build_alembic_postgres_dsn(params)
    assert "sslcert=/etc/maas/db.crt" in dsn
    assert "sslkey=/etc/maas/db.key" in dsn
    assert "sslrootcert=/etc/maas/ca.crt" in dsn


def test_build_alembic_postgres_dsn_rootcert_only():
    """CA cert present without client cert → sslrootcert in DSN, no sslcert/sslkey."""
    params = {
        "host": "pg.internal",
        "port": "5432",
        "dbname": "maasdb",
        "user": "maas",
        "password": "",
        "sslmode": "verify-ca",
        "sslrootcert": "/etc/maas/ca.crt",
    }
    dsn = Command._build_alembic_postgres_dsn(params)
    assert "sslrootcert=/etc/maas/ca.crt" in dsn
    assert "sslcert=" not in dsn
    assert "sslkey=" not in dsn


def test_build_alembic_postgres_dsn_no_certs_no_cert_params():
    params = {
        "host": "pg.internal",
        "port": "5432",
        "dbname": "maasdb",
        "user": "maas",
        "password": "",
        "sslmode": "require",
    }
    dsn = Command._build_alembic_postgres_dsn(params)
    assert "sslcert=" not in dsn
    assert "sslkey=" not in dsn
    assert "sslrootcert=" not in dsn
