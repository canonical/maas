from functools import lru_cache

from fixtures import Fixture

from provisioningserver.certificates import Certificate
from provisioningserver.utils.fs import atomic_write


@lru_cache(maxsize=5)
def get_sample_cert(name: str = "maas", *args, **kwargs) -> Certificate:
    """Return a sample Certificate for tests."""
    return Certificate.generate(name, *args, **kwargs)


@lru_cache(maxsize=1)
def get_sample_cert_with_cacerts() -> Certificate:
    """Return a sample Certificate with CA material for tests."""
    cert = get_sample_cert()
    ca_cert = get_sample_cert(name="CA")
    return Certificate.from_pem(
        cert.private_key_pem(),
        cert.certificate_pem(),
        ca_certs_material=ca_cert.certificate_pem(),
    )


class SampleCertificateFixture(Fixture):
    def __init__(self, cache_path):
        super().__init__()
        self.cache_path = cache_path

    def _setUp(self):
        if self.cache_path.exists():
            cert = Certificate.from_pem(self.cache_path.read_text())
        else:
            cert = get_sample_cert()
            cert_pem = cert.certificate_pem()
            key_pem = cert.private_key_pem()
            atomic_write(
                cert_pem.encode("ascii") + key_pem.encode("ascii"),
                self.cache_path,
            )
        self.cert = cert
