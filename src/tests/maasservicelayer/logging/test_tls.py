#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
"""Unit tests for maasservicelayer.logging.tls."""

import logging
from unittest.mock import MagicMock

from yarl import URL

from maasservicelayer.logging.tls import fips_tls_trace_config


class _FakeSSLObject:
    def cipher(self):
        return ("ECDHE-RSA-AES256-GCM-SHA384", "TLSv1.3", 256)

    def getpeercert(self):
        return {"issuer": ((("commonName", "My CA"),),)}

    def version(self):
        return "TLSv1.3"


def _make_params(url: str, ssl_object) -> MagicMock:
    transport = MagicMock()
    transport.get_extra_info.return_value = ssl_object
    connection = MagicMock()
    connection.transport = transport
    params = MagicMock()
    params.response.connection = connection
    params.url = URL(url)
    return params


class TestFipsTlsTraceConfig:
    async def test_logs_negotiated_handshake_when_fips(self, caplog, mocker):
        mocker.patch("maascommon.fips.is_fips_enabled", return_value=True)
        trace_config = fips_tls_trace_config()
        handler = trace_config.on_request_end[0]
        params = _make_params("https://example.com/path", _FakeSSLObject())

        with caplog.at_level(logging.INFO, logger="maas.fips"):
            await handler(MagicMock(), MagicMock(), params)

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.__dict__["peer"] == "example.com:443"
        assert record.__dict__["cipher_suite"] == "ECDHE-RSA-AES256-GCM-SHA384"
        assert record.__dict__["cert_issuer"] == "My CA"

    async def test_noop_for_plain_http(self, caplog, mocker):
        mocker.patch("maascommon.fips.is_fips_enabled", return_value=True)
        trace_config = fips_tls_trace_config()
        handler = trace_config.on_request_end[0]
        # A plain-HTTP transport exposes no ssl_object.
        params = _make_params("http://example.com/path", None)

        with caplog.at_level(logging.INFO, logger="maas.fips"):
            await handler(MagicMock(), MagicMock(), params)

        assert caplog.records == []

    async def test_noop_when_not_fips(self, caplog, mocker):
        mocker.patch("maascommon.fips.is_fips_enabled", return_value=False)
        trace_config = fips_tls_trace_config()
        handler = trace_config.on_request_end[0]
        params = _make_params("https://example.com/path", _FakeSSLObject())

        with caplog.at_level(logging.INFO, logger="maas.fips"):
            await handler(MagicMock(), MagicMock(), params)

        assert caplog.records == []
