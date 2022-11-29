import pytest

from maasserver.certificates import get_maas_certificate
from maasserver.secrets import SecretManager
from provisioningserver.testing.certificates import (
    get_sample_cert_with_cacerts,
)


@pytest.mark.usefixtures("maasdb")
class TestGetMAASCertificate:
    def test_no_secret(self):
        assert (
            SecretManager().get_composite_secret("tls", default=None) is None
        )
        assert get_maas_certificate() is None

    def test_no_all_entries_secret(self):
        SecretManager().set_composite_secret("tls", {"cert": "ABC"})
        assert get_maas_certificate() is None

    def test_certificate(self):
        cert = get_sample_cert_with_cacerts()
        SecretManager().set_composite_secret(
            "tls",
            {
                "cert": cert.certificate_pem(),
                "key": cert.private_key_pem(),
                "cacert": cert.ca_certificates_pem(),
            },
        )
        maas_cert = get_maas_certificate()
        assert maas_cert is not None
        assert maas_cert.certificate_pem() == cert.certificate_pem()
        assert maas_cert.private_key_pem() == cert.private_key_pem()
        assert maas_cert.ca_certificates_pem() == cert.ca_certificates_pem()
