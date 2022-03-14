# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""X509 certificates."""

from datetime import datetime, timedelta
import os
from pathlib import Path
import random
import secrets
from tempfile import mkstemp
from typing import NamedTuple, Optional, Tuple

from OpenSSL import crypto

from provisioningserver.path import get_tentative_data_path
from provisioningserver.utils.snap import running_in_snap, SnapPaths


class CertificateError(Exception):
    """Error handling certificates and keys."""


class Certificate(NamedTuple):
    """A self-signed X509 certificate with an associated key."""

    key: crypto.PKey
    cert: crypto.X509

    @classmethod
    def from_pem(cls, *materials: str):
        """Return a Certificate from PEM encoded material.

        The `materials` items are concatened and they are expected to contain a
        certificate and its private key.
        """
        material = "\n".join(materials)

        def no_passphrase(fileno):
            raise CertificateError("Private key can't have a passphrase")

        try:
            key = crypto.load_privatekey(
                crypto.FILETYPE_PEM, material, passphrase=no_passphrase
            )
            cert = crypto.load_certificate(crypto.FILETYPE_PEM, material)
        except crypto.Error:
            raise CertificateError("Invalid PEM material")
        cls._check_key_match(key, cert)
        return cls(key, cert)

    @classmethod
    def generate(
        cls,
        cn,
        organization_name=None,
        organizational_unit_name=None,
        key_bits=4096,
        validity=timedelta(days=3650),
    ):
        """Low-level method for generating an X509 certificate.

        This should only be used in test and in cases where you don't have
        access to the database.

        Most MAAS code should use
        maasserver.utils.certificate.generate_certificate() for generating a
        certificate, so that the parameters get set properly.
        """
        key = crypto.PKey()
        key.generate_key(crypto.TYPE_RSA, key_bits)

        cert = crypto.X509()
        cert.get_subject().CN = cn[:64]
        if organization_name:
            cert.get_issuer().organizationName = organization_name[:64]
        if organizational_unit_name:
            cert.get_issuer().organizationalUnitName = (
                organizational_unit_name[:64]
            )
        cert.set_serial_number(random.randint(0, (1 << 128) - 1))
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(int(validity.total_seconds()))
        cert.set_pubkey(key)
        cert.sign(key, "sha512")
        return cls(key, cert)

    def cn(self) -> str:
        """Return the certificate CN."""
        return self.cert.get_subject().CN

    def o(self) -> str:
        """Return the certificate O."""
        return self.cert.get_issuer().O

    def ou(self) -> str:
        """Return the certificate OU."""
        return self.cert.get_issuer().OU

    def expiration(self) -> Optional[datetime]:
        """Return the certificate expiration."""
        expiry = self.cert.get_notAfter()
        if expiry is None:
            return None
        return datetime.strptime(expiry.decode("ascii"), "%Y%m%d%H%M%SZ")

    def public_key_pem(self) -> str:
        """Return PEM-encoded public key."""
        return crypto.dump_publickey(crypto.FILETYPE_PEM, self.key).decode(
            "ascii"
        )

    def private_key_pem(self) -> str:
        """Return PEM-encoded private key."""
        return crypto.dump_privatekey(crypto.FILETYPE_PEM, self.key).decode(
            "ascii"
        )

    def certificate_pem(self) -> str:
        """Return PEM-encoded certificate."""
        return crypto.dump_certificate(crypto.FILETYPE_PEM, self.cert).decode(
            "ascii"
        )

    def cert_hash(self) -> str:
        """Return the SHA-256 digest for the certificate."""
        return self.cert.digest("sha256").decode("ascii")

    def tempfiles(self) -> Tuple[str, str]:
        """Return a 2-tuple with paths for tempfiles containing cert and key."""

        def write_temp(content: str) -> str:
            fileno, path = mkstemp()
            os.write(fileno, bytes(content, "ascii"))
            os.close(fileno)
            return path

        return (
            write_temp(self.certificate_pem()),
            write_temp(self.private_key_pem()),
        )

    @staticmethod
    def _check_key_match(key, cert):
        data = secrets.token_bytes()
        signature = crypto.sign(key, data, "sha512")
        try:
            crypto.verify(cert, signature, data, "sha512")
        except crypto.Error:
            raise CertificateError("Private and public keys don't match")


def get_maas_cert_tuple():
    """Return a 2-tuple with certificate and private key paths.

    The format is the same used by python-requests."""
    if running_in_snap():
        cert_dir = SnapPaths.from_environ().common / "certificates"
        private_key = cert_dir / "maas.key"
        certificate = cert_dir / "maas.crt"
    else:
        private_key = Path(
            get_tentative_data_path("/etc/maas/certificates/maas.key")
        )
        certificate = Path(
            get_tentative_data_path("/etc/maas/certificates/maas.crt")
        )
    if not private_key.exists() or not certificate.exists():
        return None
    return str(certificate), str(private_key)
