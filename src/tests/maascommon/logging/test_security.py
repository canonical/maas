#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
"""Unit tests for maascommon.logging.security."""

import logging

from maascommon.logging.security import (
    FIPS_CRYPTO_ERROR,
    FIPS_DRIVER_REJECTED,
    FIPS_SSH_AUTHENTICATION,
    FIPS_TLS_HANDSHAKE,
    log_fips_crypto_error,
    log_fips_driver_rejected,
    log_fips_ssh_authentication,
    log_fips_tls_handshake,
    log_fips_tls_handshake_from_sslobj,
)


class _FakeSSLObject:
    def __init__(self, cipher=None, peercert=None, version="TLSv1.3"):
        self._cipher = cipher
        self._peercert = peercert
        self._version = version

    def cipher(self):
        return self._cipher

    def getpeercert(self):
        return self._peercert

    def version(self):
        return self._version


class TestLogFipsTlsHandshake:
    def test_emits_info_on_maas_fips_logger(self, caplog):
        with caplog.at_level(logging.INFO, logger="maas.fips"):
            log_fips_tls_handshake(
                cipher_suite="ECDHE-RSA-AES256-GCM-SHA384",
                protocol_version="TLSv1.3",
                peer="10.0.0.1:443",
                cert_issuer="CN=My CA",
                cert_valid=True,
            )
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.levelno == logging.INFO
        assert FIPS_TLS_HANDSHAKE in record.message
        assert record.event == FIPS_TLS_HANDSHAKE
        assert record.cipher_suite == "ECDHE-RSA-AES256-GCM-SHA384"
        assert record.protocol_version == "TLSv1.3"
        assert record.peer == "10.0.0.1:443"
        assert record.cert_issuer == "CN=My CA"
        assert record.cert_valid is True


class TestLogFipsSshAuthentication:
    def test_emits_info_on_maas_fips_logger(self, caplog):
        with caplog.at_level(logging.INFO, logger="maas.fips"):
            log_fips_ssh_authentication(
                key_type="ecdsa-sha2-nistp256",
                kex="ecdh-sha2-nistp256",
                cipher="aes256-ctr",
                mac="hmac-sha2-256",
                peer="10.0.0.2",
                result="success",
            )
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.levelno == logging.INFO
        assert FIPS_SSH_AUTHENTICATION in record.message
        assert record.event == FIPS_SSH_AUTHENTICATION
        assert record.key_type == "ecdsa-sha2-nistp256"
        assert record.kex == "ecdh-sha2-nistp256"
        assert record.cipher == "aes256-ctr"
        assert record.mac == "hmac-sha2-256"
        assert record.peer == "10.0.0.2"
        assert record.result == "success"


class TestLogFipsCryptoError:
    def test_emits_error_on_maas_fips_logger(self, caplog):
        with caplog.at_level(logging.ERROR, logger="maas.fips"):
            log_fips_crypto_error(
                operation="tls_handshake",
                error="weak cipher",
                algorithm="RC4",
                peer="10.0.0.5",
            )
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.levelno == logging.ERROR
        assert FIPS_CRYPTO_ERROR in record.message
        assert record.event == FIPS_CRYPTO_ERROR
        assert record.operation == "tls_handshake"
        assert record.error == "weak cipher"
        assert record.algorithm == "RC4"
        assert record.peer == "10.0.0.5"

    def test_peer_defaults_to_empty_string(self, caplog):
        with caplog.at_level(logging.ERROR, logger="maas.fips"):
            log_fips_crypto_error(
                operation="key_generation",
                error="DSA not permitted",
                algorithm="dsa",
            )
        assert caplog.records[0].peer == ""


class TestLogFipsDriverRejected:
    def test_emits_error_on_maas_fips_logger(self, caplog):
        with caplog.at_level(logging.ERROR, logger="maas.fips"):
            log_fips_driver_rejected(
                driver="apc",
                reason="SNMPv1 — no FIPS-approved authentication",
            )
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.levelno == logging.ERROR
        assert FIPS_DRIVER_REJECTED in record.message
        assert record.event == FIPS_DRIVER_REJECTED
        assert record.driver == "apc"
        assert record.reason == "SNMPv1 — no FIPS-approved authentication"


class TestLogFipsTlsHandshakeFromSslobj:
    def test_noop_when_ssl_object_is_none(self, caplog, mocker):
        mocker.patch("maascommon.fips.is_fips_enabled", return_value=True)
        with caplog.at_level(logging.INFO, logger="maas.fips"):
            log_fips_tls_handshake_from_sslobj(None, peer="10.0.0.1:443")
        assert caplog.records == []

    def test_noop_when_not_fips(self, caplog, mocker):
        mocker.patch("maascommon.fips.is_fips_enabled", return_value=False)
        ssl_object = _FakeSSLObject(
            cipher=("ECDHE-RSA-AES256-GCM-SHA384", "TLSv1.3", 256),
        )
        with caplog.at_level(logging.INFO, logger="maas.fips"):
            log_fips_tls_handshake_from_sslobj(ssl_object, peer="10.0.0.1:443")
        assert caplog.records == []

    def test_emits_negotiated_values_when_fips(self, caplog, mocker):
        mocker.patch("maascommon.fips.is_fips_enabled", return_value=True)
        ssl_object = _FakeSSLObject(
            cipher=("ECDHE-RSA-AES256-GCM-SHA384", "TLSv1.3", 256),
            peercert={"issuer": (((("commonName", "My CA"),),))},
            version="TLSv1.3",
        )
        with caplog.at_level(logging.INFO, logger="maas.fips"):
            log_fips_tls_handshake_from_sslobj(ssl_object, peer="10.0.0.1:443")
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert FIPS_TLS_HANDSHAKE in record.message
        assert record.event == FIPS_TLS_HANDSHAKE
        assert record.cipher_suite == "ECDHE-RSA-AES256-GCM-SHA384"
        assert record.protocol_version == "TLSv1.3"
        assert record.peer == "10.0.0.1:443"
        assert record.cert_issuer == "My CA"
        assert record.cert_valid is True

    def test_unknown_values_when_cert_absent(self, caplog, mocker):
        mocker.patch("maascommon.fips.is_fips_enabled", return_value=True)
        # verify=False connections yield an empty peer cert dict.
        ssl_object = _FakeSSLObject(cipher=None, peercert={}, version=None)
        with caplog.at_level(logging.INFO, logger="maas.fips"):
            log_fips_tls_handshake_from_sslobj(ssl_object, peer="10.0.0.1:443")
        record = caplog.records[0]
        assert FIPS_TLS_HANDSHAKE in record.message
        assert record.event == FIPS_TLS_HANDSHAKE
        assert record.cipher_suite == "unknown"
        assert record.protocol_version == "unknown"
        assert record.peer == "10.0.0.1:443"
        assert record.cert_issuer == "unknown"
        assert record.cert_valid is False
