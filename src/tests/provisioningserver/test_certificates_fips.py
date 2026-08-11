# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

from OpenSSL import crypto
import pytest

from provisioningserver.certificates import (
    _validate_fips_key,
    CertificateError,
)


class TestFIPSKeyValidation:
    @pytest.fixture(autouse=True)
    def enable_fips(self, monkeypatch):
        monkeypatch.setattr(
            "provisioningserver.certificates.is_fips_enabled",
            lambda: True,
        )

    def test_allows_rsa_2048(self) -> None:
        mock_key = Mock(spec=crypto.PKey)
        mock_key.type.return_value = crypto.TYPE_RSA
        mock_key.bits.return_value = 2048
        _validate_fips_key(mock_key)

    def test_allows_rsa_4096(self) -> None:
        mock_key = Mock(spec=crypto.PKey)
        mock_key.type.return_value = crypto.TYPE_RSA
        mock_key.bits.return_value = 4096
        _validate_fips_key(mock_key)

    def test_rejects_rsa_1024(self) -> None:
        mock_key = Mock(spec=crypto.PKey)
        mock_key.type.return_value = crypto.TYPE_RSA
        mock_key.bits.return_value = 1024
        with pytest.raises(CertificateError) as exc_info:
            _validate_fips_key(mock_key)
        assert "2048" in str(exc_info.value)

    def test_rejects_dsa(self) -> None:
        mock_key = Mock(spec=crypto.PKey)
        mock_key.type.return_value = crypto.TYPE_DSA
        mock_key.bits.return_value = 2048
        with pytest.raises(CertificateError) as exc_info:
            _validate_fips_key(mock_key)
        assert "DSA" in str(exc_info.value)
