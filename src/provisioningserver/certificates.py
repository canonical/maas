# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""X509 certificates."""

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import random
import re
import secrets
from tempfile import mkstemp
from typing import NamedTuple, Optional, Self, Tuple

from OpenSSL import crypto

from provisioningserver.path import get_tentative_data_path
from provisioningserver.utils.fs import atomic_write
from provisioningserver.utils.snap import running_in_snap, SnapPaths

# inspired by https://github.com/hynek/pem
CERTS_RE = re.compile(
    """----[- ]BEGIN CERTIFICATE[- ]----\r?
.+?\r?
----[- ]END CERTIFICATE[- ]----\r?\n?""",
    re.DOTALL,
)


class CertificateError(Exception):
    """Error handling certificates and keys."""


class CertificateRequest(NamedTuple):
    key: crypto.PKey
    csr: crypto.X509Req

    @classmethod
    def generate(
        cls,
        cn: str,
        organization_name: Optional[str] = None,
        organizational_unit_name: Optional[str] = None,
        key_bits: int = 4096,
        subject_alternative_name: bytes | None = None,
    ):
        key = crypto.PKey()
        key.generate_key(crypto.TYPE_RSA, key_bits)

        csr = crypto.X509Req()
        csr.get_subject().CN = cn[:64]
        if organization_name:
            csr.get_subject().organizationName = organization_name[:64]
        if organizational_unit_name:
            csr.get_subject().organizationalUnitName = (
                organizational_unit_name[:64]
            )
        csr.set_pubkey(key)

        if subject_alternative_name:
            csr.add_extensions(
                [
                    crypto.X509Extension(
                        b"subjectAltName", False, subject_alternative_name
                    )
                ]
            )
        csr.sign(key, "sha512")
        return cls(key, csr)


class Certificate(NamedTuple):
    """A self-signed X509 certificate with an associated key."""

    key: crypto.PKey
    cert: crypto.X509
    ca_certs: Tuple[crypto.X509]

    @classmethod
    def from_pem(cls, *materials: str, ca_certs_material: str = "") -> Self:
        """Return a Certificate from PEM encoded material.

        The `materials` items are concatened and they are expected to contain a
        certificate and its private key.

        Optionally, it's possible to pass a string containing a set of CA
        certificates.
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

        ca_certs = cls._split_ca_certs(ca_certs_material)
        return cls(key, cert, ca_certs)

    @classmethod
    def _build_base_certificate(
        cls,
        key: crypto.PKey,
        version: crypto.x509.Version,
        validity: timedelta,
    ) -> crypto.X509:
        cert = crypto.X509()
        cert.set_version(version.value)
        cert.set_serial_number(random.randint(0, (1 << 128) - 1))
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(int(validity.total_seconds()))
        cert.set_pubkey(key)
        return cert

    @classmethod
    def generate(
        cls,
        cn: str,
        organization_name: Optional[str] = None,
        organizational_unit_name: Optional[str] = None,
        key_bits: int = 4096,
        validity: timedelta = timedelta(days=3650),
    ) -> Self:
        """Low-level method for generating an X509 certificate.

        This should only be used in test and in cases where you don't have
        access to the database.

        Most MAAS code should use
        maasserver.utils.certificate.generate_certificate() for generating a
        certificate, so that the parameters get set properly.
        """
        key = crypto.PKey()
        key.generate_key(crypto.TYPE_RSA, key_bits)

        cert = cls._build_base_certificate(
            key, crypto.x509.Version.v1, validity
        )
        cert.get_subject().CN = cn[:64]
        if organization_name:
            cert.get_issuer().organizationName = organization_name[:64]
        if organizational_unit_name:
            cert.get_issuer().organizationalUnitName = (
                organizational_unit_name[:64]
            )

        cert.sign(key, "sha512")
        return cls(key, cert, ())

    @classmethod
    def generate_ca_certificate(
        cls,
        cn: str,
        organization_name: Optional[str] = None,
        organizational_unit_name: Optional[str] = None,
        key_bits: int = 4096,
        validity: timedelta = timedelta(days=3650),
    ) -> Self:
        """Low-level method for generating a root X509 certificate.

        This should only be used in test and in cases where you don't have
        access to the database. Use maasserver.utils.certificate.generate_ca_certificate() instead.
        """
        key = crypto.PKey()
        key.generate_key(crypto.TYPE_RSA, key_bits)

        cert = cls._build_base_certificate(
            key, crypto.x509.Version.v3, validity
        )
        cert.get_subject().CN = cn[:64]
        if organization_name:
            cert.get_issuer().organizationName = organization_name[:64]
        if organizational_unit_name:
            cert.get_issuer().organizationalUnitName = (
                organizational_unit_name[:64]
            )
        cert.set_issuer(cert.get_subject())

        # This is a must for self-signed certificates.
        cert.add_extensions(
            [crypto.X509Extension(b"basicConstraints", True, b"CA:TRUE")]
        )
        cert.sign(key, "sha512")
        return cls(key, cert, ())

    def sign_certificate_request(
        self,
        certificate_request: CertificateRequest,
        validity: timedelta = timedelta(days=3650),
    ) -> Self:
        """
        Sign a certificate request with the CA's private key.

        This method signs the provided certificate request with the Certificate Authority (CA)'s
        private key and returns the signed certificate.

        Parameters:
            certificate_request (CertificateRequest): The certificate request to sign.
            validity (timedelta): The validity period for the signed certificate. Default is 10 years.

        Returns:
            Certificate: The signed certificate.
        """
        cert = Certificate._build_base_certificate(
            certificate_request.key, crypto.x509.Version.v3, validity
        )
        cert.set_issuer(self.cert.get_subject())
        cert.set_subject(certificate_request.csr.get_subject())
        cert.add_extensions(certificate_request.csr.get_extensions())
        cert.sign(self.key, "sha512")
        return Certificate(
            key=certificate_request.key, cert=cert, ca_certs=(self.cert,)
        )

    def cn(self) -> str:
        """Return the certificate CN."""
        return self.cert.get_subject().CN

    def o(self) -> str:
        """Return the certificate O."""
        return self.cert.get_issuer().O

    def ou(self) -> str:
        """Return the certificate OU."""
        return self.cert.get_issuer().OU

    def _parse_datetime(self, date) -> Optional[datetime]:
        if date is None:
            return None
        return datetime.strptime(
            date.decode("ascii"), "%Y%m%d%H%M%SZ"
        ).replace(tzinfo=timezone.utc)

    def expiration(self) -> Optional[datetime]:
        """Return the certificate expiration."""
        return self._parse_datetime(self.cert.get_notAfter())

    def not_before(self) -> Optional[datetime]:
        """Return the certificate `not before` date."""
        return self._parse_datetime(self.cert.get_notBefore())

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

    def ca_certificates_pem(self) -> str:
        """Return PEM-encoded CA certificates chain"""
        return b"".join(
            crypto.dump_certificate(crypto.FILETYPE_PEM, ca_cert)
            for ca_cert in self.ca_certs
        ).decode("ascii")

    def fullchain_pem(self) -> str:
        """Return PEM-encoded full chain (certificate + CA certificates)."""
        return self.certificate_pem() + self.ca_certificates_pem()

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
    def _check_key_match(key: crypto.PKey, cert: crypto.X509):
        data = secrets.token_bytes()
        signature = crypto.sign(key, data, "sha512")
        try:
            crypto.verify(cert, signature, data, "sha512")
        except crypto.Error:
            raise CertificateError("Private and public keys don't match")

    @staticmethod
    def _split_ca_certs(ca_certs_material: str) -> Tuple[crypto.X509]:
        return tuple(
            crypto.load_certificate(crypto.FILETYPE_PEM, material)
            for material in CERTS_RE.findall(ca_certs_material)
        )


def get_cluster_certificates_path() -> Path:
    maas_root = os.getenv("MAAS_ROOT", "/var/lib/maas")
    return Path(maas_root) / "certificates"


def get_maas_cluster_cert_paths() -> tuple[str, str, str] | None:
    """Return a 2-tuple with certificate and private key paths for the cluster certificates."""

    cert_dir = get_cluster_certificates_path()
    private_key = cert_dir / "cluster.key"
    certificate = cert_dir / "cluster.pem"
    cacerts = cert_dir / "cacerts.pem"
    if (
        not private_key.exists()
        or not certificate.exists()
        or not cacerts.exists()
    ):
        return None
    return str(certificate), str(private_key), str(cacerts)


def store_maas_cluster_cert_tuple(
    private_key: bytes, certificate: bytes, cacerts: bytes
) -> None:
    """
    Stores the private key and the certificate on the disk.
    """

    cert_dir = get_cluster_certificates_path()
    atomic_write(
        private_key,
        cert_dir / "cluster.key",
        overwrite=True,
        mode=0o600,
    )

    atomic_write(
        certificate,
        cert_dir / "cluster.pem",
        overwrite=True,
        mode=0o644,
    )

    atomic_write(
        cacerts,
        cert_dir / "cacerts.pem",
        overwrite=True,
        mode=0o644,
    )


def get_maas_cert_tuple():
    """Return a 2-tuple with certificate and private key paths.

    The format is the same used by python-requests."""
    if running_in_snap():
        cert_dir = SnapPaths.from_environ().common / "certificates"
    else:
        cert_dir = Path(get_tentative_data_path("/etc/maas/certificates"))

    private_key = cert_dir / "maas.key"
    certificate = cert_dir / "maas.crt"
    if not private_key.exists() or not certificate.exists():
        return None
    return str(certificate), str(private_key)
