import os
from typing import Iterable, List

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from temporalio.api.common.v1 import Payload
from temporalio.converter import PayloadCodec

METADATA_ENCODING_ENCRYPTED = "binary/encrypted"


class EncryptionCodec(PayloadCodec):
    def __init__(self, key: bytes) -> None:
        super().__init__()
        self.encryptor = AESGCM(key)

    async def encode(self, payloads: Iterable[Payload]) -> List[Payload]:
        return [
            Payload(
                metadata={
                    "encoding": bytes(METADATA_ENCODING_ENCRYPTED, "utf-8")
                },
                data=self.encrypt(p.SerializeToString()),
            )
            for p in payloads
        ]

    async def decode(self, payloads: Iterable[Payload]) -> List[Payload]:
        ret: List[Payload] = []
        for p in payloads:
            # Ignore ones without expected encoding
            if (
                p.metadata.get("encoding", b"").decode()
                != METADATA_ENCODING_ENCRYPTED
            ):
                ret.append(p)
                continue

            ret.append(Payload.FromString(self.decrypt(p.data)))
        return ret

    def encrypt(self, data: bytes) -> bytes:
        nonce = os.urandom(12)
        return nonce + self.encryptor.encrypt(nonce, data, None)

    def decrypt(self, data: bytes) -> bytes:
        return self.encryptor.decrypt(data[:12], data[12:], None)
