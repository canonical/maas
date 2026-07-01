# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock, patch

from cryptography.hazmat.primitives.asymmetric.dsa import DSAPublicKey
import pytest

from maasservicelayer.builders.sslkeys import SSLKeyBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.sslkeys import SSLKeysRepository
from maasservicelayer.exceptions.catalog import FIPSViolationException
from maasservicelayer.services.sslkey import SSLKeysService


@pytest.mark.asyncio
class TestSSLKeysServiceFIPSValidation:
    @pytest.fixture(autouse=True)
    def enable_fips(self, monkeypatch):
        monkeypatch.setattr(
            "maasservicelayer.services.sslkey.is_fips_enabled",
            lambda: True,
        )

    async def test_fips_rejects_dsa_cert(self) -> None:
        repository = Mock(SSLKeysRepository)
        repository.exists.return_value = False
        service = SSLKeysService(
            context=Context(), sslkey_repository=repository
        )

        dsa_cert = """-----BEGIN CERTIFICATE-----
MIIDXTCCAkWgAwIBAgIJAJC1HiIAZAiUMA0GCSqGSIb3DQEBBQUAMEUxCzAJBgNV
BAYTAkFVMRMwEQYDVQQIDApTb21lLVN0YXRlMSEwHwYDVQQKDBhJbnRlcm5ldCBX
aWRnaXRzIFB0eSBMdGQwHhcNMTMwOTI5MTEzNzAyWhcNMTQwOTI5MTEzNzAyWjBF
MQswCQYDVQQGEwJBVTETMBEGA1UECAwKU29tZS1TdGF0ZTEhMB8GA1UECgwYSW50
ZXJuZXQgV2lkZ2l0cyBQdHkgTHRkMIIBSzCCAQMGByqGSM44BAEwggE6AoGBANv
GyGM7XCvgEN7fZ0p4D5La1x8d3YbC1EKRfVUqMfxBZd4Yj3qxSOxD4Ww5i1vQ5v
7Lx6hMGLMZLHoSmNfJJyqH8F+bK3ZTfAWSM3dF3zL/cx3Z3y7r8G7m3c7h0P9x0
J+WyZ9dKjYlT+djF0z1i3n1n8L5d3P9Q0f1k3m2n1Q2AkAFxL5qL6q7q8q9r0s1
t2u3v4w5x6y7z8A9B0C1D2E3F4G5H6I7J8K9L0M1N2O3P4Q5R6S7T8U9V0W1X2Y3Z4
a5b6c7d8e9f0g1h2i3j4k5l6m7n8o9p0q1r2s3t4u5v6w7x8y9z0A1B2C3D4E5F6G7
H8I9J0K1L2M3N4O5P6Q7R8S9T0U1V2W3X4Y5Z6a7b8c9d0e1f2g3h4i5j6k7l8m9n0o1p
q2r3s4t5u6v7w8x9y0z1A2B3C4D5E6F7G8H9I0J1K2L3M4N5O6P7Q8R9S0T1U2V3W4X5
Y6Z7a8b9c0d1e2f3g4h5i6j7k8l9m0n1o2p3q4r5s6t7u8v9w0x1y2z3A4B5C6D7E8F9
G0H1I2J3K4L5M6N7O8P9Q0R1S2T3U4V5W6X7Y8Z9a0b1c2d3e4f5g6h7i8j9k0l1m2n3
o4p5q6r7s8t9u0v1w2x3y4z5A6B7C8D9E0F1G2H3I4J5K6L7M8N9O0P1Q2R3S4T5U6V7
W8X9Y0Z1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v3w4x5y6z7A8B9C0D1
E2F3G4H5I6J7K8L9M0N1O2P3Q4R5S6T7U8V9W0X1Y2Z3a4b5c6d7e8f9g0h1i2j3k4l5
m6n7o8p9q0r1s2t3u4v5w6x7y8z9A0B1C2D3E4F5G6H7I8J9K0L1M2N3O4P5Q6Q7R8S9
T0U1V2W3X4Y5Z6a7b8c9d0e1f2g3h4i5j6k7l8m9n0o1p2q3r4s5t6u7v8w9x0y1z2A3
B4C5D6E7F8G9H0I1J2K3L4M5N6O7P8Q9R0S1T2U3V4W5X6Y7Z8a9b0c1d2e3f4g5h6i7
j8k9l0m1n2o3p4q5r6s7t8u9v0w1x2y3z4A5B6C7D8E9F0G1H2I3J4K5L6M7N8O9P0Q1
R2S3T4U5V6W7X8Y9Z0a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5
z6A7B8C9D0E1F2G3H4I5J6K7L8M9N0O1P2Q3R4S5T6U7V8W9X0Y1Z2a3b4c5d6e7f8g9
h0i1j2k3l4m5n6o7p8q9r0s1t2u3v4w5x6y7z8A9B0C1D2E3F4G5H6I7J8K9L0M1N2O3
P4Q5R6S7T8U9V0W1X2Y3Z4a5b6c7d8e9f0g1h2i3j4k5l6m7n8o9p0q1r2s3t4u5v6w7
x8y9z0A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8S9T0U1V2W3X4Y5Z6a7b8c9d0e1
f2g3h4i5j6k7l8m9n0o1p2q3r4s5t6u7v8w9x0y1z2A3B4C5D6E7F8G9H0I1J2K3L4M5
N6O7P8Q9R0S1T2U3V4W5X6Y7Z8a9b0c1d2e3f4g5h6i7j8k9l0m1n2o3p4q5r6s7t8u9
v0w1x2y3z4A5B6C7D8E9F0G1H2I3J4K5L6M7N8O9P0Q1R2S3T4U5V6W7X8Y9Z0a1b2c3
d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6A7B8C9D0E1F2G3H4I5J6K7
L8M9N0O1P2Q3R4S5T6U7V8W9X0Y1Z2a3b4c5d6e7f8g9h0i1j2k3l4m5n6o7p8q9r0s1
t2u3v4w5x6y7z8A9B0C1D2E3F4G5H6I7J8K9L0M1N2O3P4Q5R6S7T8U9V0W1X2Y3Z4
a5b6c7d8e9f0g1h2i3j4k5l6m7n8o9p0q1r2s3t4u5v6w7x8y9z0A1B2C3D4E5F6G7
H8I9J0K1L2M3N4O5P6Q7R8S9T0U1V2W3X4Y5Z6a7b8c9d0e1f2g3h4i5j6k7l8m9n0o1p
q2r3s4t5u6v7w8x9y0z1A2B3C4D5E6F7G8H9I0J1K2L3M4N5O6P7Q8R9S0T1U2V3W4X5
Y6Z7a8b9c0d1e2f3g4h5i6j7k8l9m0n1o2p3q4r5s6t7u8v9w0x1y2z3A4B5C6D7E8F9
G0H1I2J3K4L5M6N7O8P9Q0R1S2T3U4V5W6X7Y8Z9a0b1c2d3e4f5g6h7i8j9k0l1m2n3
o4p5q6r7s8t9u0v1w2x3y4z5A6B7C8D9E0F1G2H3I4J5K6L7M8N9O0P1Q2R3S4T5U6V7
W8X9Y0Z1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v3w4x5y6z7A8B9C0D1
E2F3G4H5I6J7K8L9M0N1O2P3Q4R5S6T7U8V9W0X1Y2Z3a4b5c6d7e8f9g0h1i2j3k4l5
m6n7o8p9q0r1s2t3u4v5w6x7y8z9A0B1C2D3E4F5G6H7I8J9K0L1M2M3N4O5P6Q7R8
S9T0U1V2W3X4Y5Z6a7b8c9d0e1f2g3h4i5j6k7l8m9n0o1p2q3r4s5t6u7v8w9x0y1z
2A3B4C5D6E7F8G9H0I1J2K3L4M5N6O7P8Q9R0S1T2U3V4W5X6Y7Z8a9b0c1d2e3f4g
5h6i7j8k9l0m1n2o3p4q5r6s7t8u9v0w1x2y3z4A5B6C7D8E9F0G1H2I3J4K5L6M7N8
O9P0Q1R2S3T4U5V6W7X8Y9Z0a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v
2w3x4y5z6A7B8C9D0E1F2G3H4I5J6K7L8M9N0O1P2Q3R4S5T6U7V8W9X0Y1Z2a3b4c5
d6e7f8g9h0i1j2k3l4m5n6o7p8q9r0s1t2u3v4w5x6y7z8A9B0C1D2E3F4G5H6I7J8
K9L0M1N2O3P4Q5R6S7T8U9V0W1X2Y3Z4a5b6c7d8e9f0g1h2i3j4k5l6m7n8o9p0q1r
2s3t4u5v6w7x8y9z0A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8S9T0U1V2W3X4Y5
Z6a7b8c9d0e1f2g3h4i5j6k7l8m9n0o1p2q3r4s5t6u7v8w9x0y1z2A3B4C5D6E7F8G9
H0I1J2K3L4M5N6O7P8Q9R0S1T2U3V4W5X6Y7Z8a9b0c1d2e3f4g5h6i7j8k9l0m1n2o3
p4q5r6s7t8u9v0w1x2y3z4A5B6C7D8E9F0G1H2I3J4K5L6M7N8O9P0Q1R2S3T4U5V6
W7X8Y9Z0a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6A7B8C9
D0E1F2G3H4I5J6K7L8M9N0O1P2Q3R4S5T6U7V8W9X0Y1Z2a3b4c5d6e7f8g9h0i1j2k
3l4m5n6o7p8q9r0s1t2u3v4w5x6y7z8A9B0C1D2E3F4G5H6I7J8K9L0M1N2O3P4Q5R6
S7T8U9V0W1X2Y3Z4a5b6c7d8e9f0g1h2i3j4k5l6m7n8o9p0q1r2s3t4u5v6w7x8y9z0
A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6P7Q8R9S0T1U2V3W4X5Y6Z7a8b9c0d1e2f3g4
h5i6j7k8l9m0n1o2p3q4r5s6t7u8v9w0x1y2z3A4B5C6D7E8F9G0H1I2J3K4L5M6N7
O8P9Q0R1S2T3U4V5W6X7Y8Z9a0b1c2d3e4f5g6h7i8j9k0l1m2n3o4p5q6r7s8t9u0v
1w2x3y4z5A6B7C8D9E0F1G2H3I4J5K6L7M8N9O0P1Q2R3S4S5T6U7V8W9X0Y1Z2a3b4
c5d6e7f8g9h0i1j2k3l4m5n6o7p8q9r0s1t2u3v4w5x6y7z8A9B0C1D2E3F4G5H6I7
J8K9L0M1N2O3P4Q5R6S7T8U9V0W1X2Y3Z4a5b6c7d8e9f0g1h2i3j4k5l6m7n8o9p0
q1r2s3t4u5v6w7x8y9z0A1B2C3C4D5E6F7G8H9I0J1K2L3M4N5O6P7Q8R9S0T1U2V3
W4X5Y6Z7a8b9c0d1e2f3g4h5i6j7k8l9m0n1o2p3q4r5s6t7u8v9w0x1y2z3A4B5C6D7
E8F9G0H1I2J3K4L5M6N7O8P9Q0R1S2T3U4V5W6X7Y8Z9a0b1c2d3e4f5g6h7i8j9k0
l1m2n3o4p5q6r7s8t9u0v1w2x3y4z5A6B7C8D9E0F1G2H3I4J5K6L7M8N9O0P1Q2R3
S4T5U6V7W8X9Y0Z1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v3w4x5y6
z7A8B9C0D1E2F3G4H5I6I7J8K9L0M1N2O3P4Q5R6S7T8U9V0W1X2Y3Z4a5b6c7d8e9
f0g1h2i3j4k5l6m7n8o9p0q1r2s3t4u5v6w7x8y9z0A1B2C3D4E5F6G7H8I9J0K1L2
M3N4O5P6Q7R8S9T0U1V2W3X4Y5Z6a7b8c9d0e1f2g3h4i5j6k7l8m9n0o1p2q3r4s5
t6u7v8w9x0y1z2A3B4C5D6E7F8G9H0I1J2K3L4M5N6O7P8Q9R0S1T2U3V4W5X6Y7Z
8a9b0c1d2e3f4g5h6i7j8k9l0m1n2o3p4q5r6s7t8u9v0w1x2y3z4A5B6C7D8E9F0
G1H2I3J4K5L6M7N8O9P0Q1R2R3S4T5U6V7W8X9Y0Z1a2b3c4d5e6f7g8h9i0j1k2l3
m4n5o6p7q8r9s0t1u2v3w4x5y6z7A8B9C0D1E2F3G4H5I6J7K8L9M0N1O2P3Q4R5
S6T7U8V9W0X1Y2Z3a4b5c6d7e8f9g0h1i2j3k4l5m6n7o8p9q0r1s2t3u4v5w6x7y8
z9A0B1C2D3E4F5G6H7I8I9J0K1L2M3N4O5P6Q7R8S9T0U1V2W3X4Y5Z6a7b8c9d0
-----END CERTIFICATE-----
        """
        # DSA cert would fail load_pem_x509_certificate, so it returns early
        # Instead test with a mocked cert
        repository = Mock(SSLKeysRepository)
        repository.exists.return_value = False
        service = SSLKeysService(
            context=Context(), sslkey_repository=repository
        )

        # Mock a DSA public key on a loaded certificate
        mock_cert = Mock()
        mock_dsa_key = Mock(spec=DSAPublicKey)
        mock_cert.public_key.return_value = mock_dsa_key
        mock_cert.signature_algorithm_oid = Mock()
        mock_cert.signature_algorithm_oid._name = "dsaWithSHA1"

        with patch(
            "cryptography.x509.load_pem_x509_certificate",
            return_value=mock_cert,
        ):
            with pytest.raises(FIPSViolationException):
                await service.pre_create_hook(
                    SSLKeyBuilder(key=dsa_cert, user_id=1)
                )

    async def test_fips_rejects_sha1_signed_cert(self) -> None:
        repository = Mock(SSLKeysRepository)
        repository.exists.return_value = False
        service = SSLKeysService(
            context=Context(), sslkey_repository=repository
        )

        mock_cert = Mock()
        mock_rsa_key = Mock()
        mock_rsa_key.__class__.__name__ = "RSAPublicKey"
        mock_cert.public_key.return_value = mock_rsa_key
        mock_cert.signature_algorithm_oid = Mock()
        mock_cert.signature_algorithm_oid._name = "sha1WithRSAEncryption"

        # Need to match one of the OID constants
        from cryptography import x509

        mock_cert.signature_algorithm_oid = (
            x509.oid.SignatureAlgorithmOID.RSA_WITH_SHA1
        )

        with patch(
            "cryptography.x509.load_pem_x509_certificate",
            return_value=mock_cert,
        ):
            with pytest.raises(FIPSViolationException):
                await service.pre_create_hook(
                    SSLKeyBuilder(key="dummy_pem", user_id=1)
                )

    async def test_fips_allows_compliant_cert(self) -> None:
        repository = Mock(SSLKeysRepository)
        repository.exists.return_value = False
        service = SSLKeysService(
            context=Context(), sslkey_repository=repository
        )

        mock_cert = Mock()
        mock_rsa_key = Mock()
        mock_rsa_key.__class__.__name__ = "RSAPublicKey"
        mock_rsa_key.key_size = 4096
        mock_cert.public_key.return_value = mock_rsa_key
        mock_cert.signature_algorithm_oid = Mock()
        mock_cert.signature_algorithm_oid._name = "sha256WithRSAEncryption"

        # Match a compliant OID
        from cryptography import x509

        mock_cert.signature_algorithm_oid = (
            x509.oid.SignatureAlgorithmOID.RSA_WITH_SHA256
        )

        with patch(
            "cryptography.x509.load_pem_x509_certificate",
            return_value=mock_cert,
        ):
            await service.pre_create_hook(
                SSLKeyBuilder(key="dummy_pem", user_id=1)
            )


@pytest.mark.asyncio
class TestSSLKeysServiceNonFIPSValidation:
    async def test_non_fips_allows_small_rsa_cert(self) -> None:
        repository = Mock(SSLKeysRepository)
        repository.exists.return_value = False
        service = SSLKeysService(
            context=Context(), sslkey_repository=repository
        )

        mock_cert = Mock()
        mock_rsa_key = Mock()
        mock_rsa_key.__class__.__name__ = "RSAPublicKey"
        mock_rsa_key.key_size = 1024
        mock_cert.public_key.return_value = mock_rsa_key
        mock_cert.signature_algorithm_oid = Mock()
        mock_cert.signature_algorithm_oid._name = "sha256WithRSAEncryption"

        from cryptography import x509

        mock_cert.signature_algorithm_oid = (
            x509.oid.SignatureAlgorithmOID.RSA_WITH_SHA256
        )

        with patch(
            "cryptography.x509.load_pem_x509_certificate",
            return_value=mock_cert,
        ):
            await service.pre_create_hook(
                SSLKeyBuilder(key="dummy_pem", user_id=1)
            )
