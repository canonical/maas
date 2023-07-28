import pytest
from temporalio.api.common.v1 import Payload
from temporalio.converter import DefaultPayloadConverter

from maasserver.workflow.codec.encryptor import (
    EncryptionCodec,
    METADATA_ENCODING_ENCRYPTED,
)


class TestEncryptionCodec:
    original = "MAAS sensitive data"
    original_payload = DefaultPayloadConverter().to_payloads((original,))

    def test_encode_empty_key(self):
        with pytest.raises(ValueError):
            _ = EncryptionCodec(b"")

    def test_encode_wrong_key_size(self):
        with pytest.raises(ValueError):
            _ = EncryptionCodec(b"incorrect size")

    @pytest.mark.asyncio
    async def test_encode_decode(self):
        # echo 'MAAS' | sha256sum | head -c 64 | tail -c 32
        key = "da720fe6ceb88077ea52c1cd737769c3".encode("utf-8")
        encryption_codec = EncryptionCodec(key)
        encoded_payload = await encryption_codec.encode(self.original_payload)

        # Used for testing EncryptionCodec in other languages
        # print("Temporal encrypted data:", encoded_payload[0].data.hex())

        decoded_payload = await encryption_codec.decode(encoded_payload)

        assert self.original_payload != encoded_payload
        assert self.original_payload == decoded_payload

    @pytest.mark.asyncio
    async def test_decode(self):
        # Decode payload encoded by EncryptionCodec implemented in Go
        # Check TestEncodeDecode in src/maasagent/pkg/workflow/codec/encryptor_test.go
        key = "d901193069ad3d2cd99ce75c303f30bc".encode("utf-8")
        encryption_codec = EncryptionCodec(key)
        data = bytes.fromhex(
            "386545e21c8599ddc8784daaef069695c1030ebc5139b365c3b53c1d98d4e2a20"
            "280c7a012ddbac1731ac0c77508b913b76fdd0ae74120b3ae2a2aad9496410acd"
            "26a3ae9f6326b5f4cf3e"
        )
        payload = Payload(
            metadata={"encoding": bytes(METADATA_ENCODING_ENCRYPTED, "utf-8")},
            data=data,
        )

        decoded_payload = await encryption_codec.decode((payload,))
        assert self.original_payload[0].data == decoded_payload[0].data
