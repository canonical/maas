# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class Encryptor:
    def __init__(self, encryption_key: bytes):
        self.encryptor = AESGCM(encryption_key)

    def encrypt(self, plaintext: str) -> str:
        nonce = os.urandom(12)
        ciphertext = self.encryptor.encrypt(nonce, plaintext.encode(), None)
        return base64.urlsafe_b64encode(nonce + ciphertext).decode()

    def decrypt(self, b64_ciphertext: str) -> str:
        data = base64.urlsafe_b64decode(b64_ciphertext.encode())
        nonce, ciphertext = data[:12], data[12:]
        return self.encryptor.decrypt(nonce, ciphertext, None).decode()
