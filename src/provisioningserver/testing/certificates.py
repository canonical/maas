from functools import lru_cache

from fixtures import Fixture

from provisioningserver.certificates import Certificate


@lru_cache()
def get_sample_cert(name: str = "maas", *args, **kwargs) -> Certificate:
    return Certificate.generate(name, *args, **kwargs)


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
            with self.cache_path.open("wb") as fh:
                fh.write(cert_pem.encode("ascii"))
                fh.write(key_pem.encode("ascii"))
        self.cert = cert
