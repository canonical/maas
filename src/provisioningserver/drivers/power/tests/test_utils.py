# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock, sentinel

import requests
from urllib3.connection import HTTPSConnection
from urllib3.util.retry import Retry

import maascommon.fips as fips_module
import maascommon.logging.security as security_module
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power import utils as utils_module


class FakeHMCSession:
    """Stand-in for a zhmcclient `Session`: exposes the same
    `_new_session()` static-method-style hook `install_fips_tls_audit_logging`
    wraps, returning a `requests.Session` with adapters mounted exactly like
    zhmcclient's real implementation does.
    """

    def __init__(self):
        self.new_session_calls = []

        def _new_session(retry_timeout_config):
            self.new_session_calls.append(retry_timeout_config)
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(
                max_retries=retry_timeout_config
            )
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            return session

        self._new_session = _new_session


class TestInstallFipsTlsAuditLogging(MAASTestCase):
    def test_noop_when_fips_disabled(self):
        self.patch(fips_module, "is_fips_enabled").return_value = False
        hmc_session = FakeHMCSession()
        original_new_session = hmc_session._new_session

        utils_module.install_fips_tls_audit_logging(
            hmc_session, "hmc.example.com"
        )

        self.assertIs(original_new_session, hmc_session._new_session)

    def test_noop_when_new_session_hook_missing(self):
        self.patch(fips_module, "is_fips_enabled").return_value = True
        hmc_session = Mock(spec=[])

        # Must not raise even though `hmc_session` has no `_new_session`.
        utils_module.install_fips_tls_audit_logging(
            hmc_session, "hmc.example.com"
        )

    def test_mounted_adapter_preserves_retry_configuration(self):
        self.patch(fips_module, "is_fips_enabled").return_value = True
        hmc_session = FakeHMCSession()
        retry_config = Retry(total=3)

        utils_module.install_fips_tls_audit_logging(
            hmc_session, "hmc.example.com"
        )
        requests_session = hmc_session._new_session(retry_config)

        https_adapter = requests_session.get_adapter("https://hmc.example.com")
        self.assertIs(retry_config, https_adapter.max_retries)
        # The http:// adapter mounted by `FakeHMCSession._new_session`
        # itself is left alone -- only https:// is intercepted.
        http_adapter = requests_session.get_adapter("http://hmc.example.com")
        self.assertIsInstance(http_adapter, requests.adapters.HTTPAdapter)
        self.assertIsNot(http_adapter, https_adapter)

    def test_connect_emits_fips_tls_handshake_audit_event(self):
        self.patch(fips_module, "is_fips_enabled").return_value = True
        mock_log = self.patch(
            security_module, "log_fips_tls_handshake_from_sslobj"
        )
        hmc_session = FakeHMCSession()

        utils_module.install_fips_tls_audit_logging(
            hmc_session, "hmc.example.com"
        )
        requests_session = hmc_session._new_session(sentinel.retry_config)
        https_adapter = requests_session.get_adapter("https://hmc.example.com")
        connection_cls = https_adapter.poolmanager.pool_classes_by_scheme[
            "https"
        ].ConnectionCls

        self.patch(HTTPSConnection, "connect")
        conn = connection_cls(host="hmc.example.com", port=6794)
        conn.sock = sentinel.ssl_socket

        conn.connect()

        mock_log.assert_called_once_with(
            sentinel.ssl_socket, peer="hmc.example.com:6794"
        )
