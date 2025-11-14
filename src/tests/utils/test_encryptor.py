# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import base64

import pytest

from maasservicelayer.utils.encryptor import Encryptor


@pytest.fixture
def encryptor() -> Encryptor:
    key = b"0" * 32
    return Encryptor(key)


class TestEncryptor:
    def test_encrypt_str_valid_return(self, encryptor: Encryptor):
        plain_text = "test"
        encrypted = encryptor.encrypt(plain_text)

        decoded = base64.urlsafe_b64decode(encrypted.encode())

        assert len(decoded) > 12
        nonce = decoded[:12]
        assert isinstance(nonce, bytes)

    def test_decrypt_str_correctly_decrypts(
        self, encryptor: Encryptor
    ) -> None:
        plain_text = "test"
        encrypted = encryptor.encrypt(plain_text)
        decrypted = encryptor.decrypt(encrypted)

        assert decrypted == plain_text
