# Copyright 2014-2016 Canonical Ltd.
# Copyright 2014 Cloudbase Solutions SRL.
# This software is licensed under the GNU Affero General Public License
# version 3 (see the file LICENSE).


import getpass
import logging
import os
from os import makedirs
import random
import socket
from string import ascii_lowercase, ascii_uppercase, digits

import OpenSSL

from provisioningserver.utils.fs import atomic_write, read_text_file

logger = logging.getLogger(__name__)


class WinRMX509Error(Exception):
    """Error when generating x509 certificate."""


class WinRMX509:
    """Generates X509 certificates compatible with Windows WinRM."""

    KEY_SIZE = 2048
    PASSPHRASE_LENGTH = 21

    def __init__(self, cert_name, upn_name=None, cert_dir=None):
        self.store = self.get_ssl_dir(cert_dir)
        self.cert_name = cert_name
        self.upn_name = upn_name
        if self.upn_name is None:
            user = getpass.getuser()
            host = socket.getfqdn()
            self.upn_name = "%s@%s" % (user, host)

        self.pem_file = os.path.join(self.store, "%s.pem" % self.cert_name)
        self.key_file = os.path.join(self.store, "%s.key" % self.cert_name)
        self.pfx_file = os.path.join(self.store, "%s.pfx" % self.cert_name)

    def create_cert(self, print_cert=False):
        """Generate a new certifficate, and save it to disk."""
        if os.path.isfile(self.pem_file):
            raise WinRMX509Error(
                "Certificate %s already exists." % self.pem_file
            )

        key, cert = self.get_key_and_cert()
        self.write_cert(cert)
        self.write_privatekey(key)

        if print_cert:
            self.print_cert_details(self.pem_file)

        logger.debug("Exporting to PKCS12")
        passwd = self.generate_passphrase()
        try:
            self.export_p12(key, cert, passwd)
            logger.debug("Passphrase for exported p12: %s" % passwd)
        except OpenSSL.crypto.Error as err:
            raise WinRMX509Error("Failed to export p12: %s" % err)

    def get_key_and_cert(self):
        """Return the private key and certificate for x509."""
        key = OpenSSL.crypto.PKey()
        key.generate_key(OpenSSL.crypto.TYPE_RSA, self.KEY_SIZE)
        cert = OpenSSL.crypto.X509()
        cert.get_subject().CN = self.upn_name
        subjectAltName = OpenSSL.crypto.X509Extension(
            b"subjectAltName",
            True,
            (
                "otherName:1.3.6.1.4.1.311.20.2.3;UTF8:%s" % self.upn_name
            ).encode("utf-8"),
        )
        key_usage = OpenSSL.crypto.X509Extension(
            b"extendedKeyUsage", True, b"clientAuth"
        )
        cert.set_serial_number(1000)
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(10 * 365 * 24 * 60 * 60)
        cert.add_extensions([subjectAltName, key_usage])
        cert.set_pubkey(key)
        cert.set_issuer(cert.get_subject())
        cert.sign(key, "sha1")
        return key, cert

    def get_cert_details(self, pem_file):
        """Return a dictionary containing X509 subject, thumbprint and
        contents."""
        cert, contents = self.load_pem_file(pem_file)
        subject = cert.get_subject().CN
        thumb = cert.digest("SHA1")
        return {"subject": subject, "thumbprint": thumb, "contents": contents}

    def write_privatekey(self, key):
        """Write the private key to disk."""
        logger.debug("Writing key: %s" % self.key_file)
        atomic_write(
            OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM, key),
            self.key_file,
        )

    def write_cert(self, cert):
        """Write the certificate to disk."""
        logger.debug("Writing certificate: %s" % self.pem_file)
        atomic_write(
            OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, cert),
            self.pem_file,
        )

    def print_cert_details(self, pem_file):
        """Print x509 details to stdout."""
        details = self.get_cert_details(pem_file)
        print("Certificate Subject: %s" % details["subject"])
        print("Certificate Thumbprint: %s" % details["thumbprint"])
        print("You may add the following cert in MAAS:")
        print(details["contents"])

    def load_pem_file(self, pem_file):
        """Load a PEM file. Returning `OpenSSL.crypto.X509` object and the
        contents of the file.

        :param pem_file: file to load
        """
        pem_data = read_text_file(pem_file)
        try:
            cert = OpenSSL.crypto.load_certificate(
                OpenSSL.crypto.FILETYPE_PEM, pem_data
            )
        except OpenSSL.crypto.Error as err:
            raise WinRMX509Error("Failed to load certificate: %s" % err)
        return cert, pem_data

    def export_p12(self, key, cert, passphrase):
        """Create a pcks12 password protected container for the generated
        certificates.

        :param key: Key file to add to PFX file
        :param cert: Certificate file to add to PFX file
        :param passphrase: export passphrase for PFX file
        """
        p12 = OpenSSL.crypto.PKCS12()
        p12.set_certificate(cert)
        p12.set_privatekey(key)
        atomic_write(
            p12.export(passphrase=bytes(passphrase.encode("utf-8"))),
            self.pfx_file,
        )

    def get_ssl_dir(self, cert_dir=None):
        """Return the directory in which to save the certificates. This also
        ensures that the directory exists.
        """
        if cert_dir is None:
            home_dir = os.path.expanduser("~")
            cert_dir = os.path.join(home_dir, ".ssl")
        makedirs(cert_dir, exist_ok=True)
        return cert_dir

    def generate_passphrase(self):
        """Generate an alphanumeric random string to be used together with
        `export_p12`.
        """
        choices = ascii_uppercase + ascii_lowercase + digits
        return "".join(
            random.choice(choices) for _ in range(self.PASSPHRASE_LENGTH)
        )
