# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Manage certificates for controllers."""

from datetime import datetime
import os
from socket import gethostname
from time import sleep

from OpenSSL import crypto

from provisioningserver.path import get_tentative_data_path
from provisioningserver.utils.fs import NamedLock
from provisioningserver.utils.snappy import (
    get_snap_common_path,
    running_in_snap,
)

if running_in_snap():
    MAAS_PRIVATE_KEY = os.path.join(
        get_snap_common_path(), "certificates", "maas.key"
    )
    MAAS_PUBLIC_KEY = os.path.join(
        get_snap_common_path(), "certificates", "maas.pub"
    )
    MAAS_CERTIFICATE = os.path.join(
        get_snap_common_path(), "certificates", "maas.crt"
    )
else:
    MAAS_PRIVATE_KEY = get_tentative_data_path(
        "/etc/maas/certificates/maas.key"
    )
    MAAS_PUBLIC_KEY = get_tentative_data_path(
        "/etc/maas/certificates/maas.pub"
    )
    MAAS_CERTIFICATE = get_tentative_data_path(
        "/etc/maas/certificates/maas.crt"
    )


def generate_rsa_keys_if_needed():
    """Generate RSA keys for MAAS.

    Returns True if a new RSA key was generated.
    """
    if os.path.isfile(MAAS_PRIVATE_KEY):
        return False
    try:
        with NamedLock("RSA"):
            os.makedirs(os.path.dirname(MAAS_PRIVATE_KEY), exist_ok=True)
            pkey = crypto.PKey()
            pkey.generate_key(crypto.TYPE_RSA, 4096)
            with open(MAAS_PRIVATE_KEY, "wb") as f:
                f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, pkey))
            os.chmod(MAAS_PRIVATE_KEY, 0o600)
            with open(MAAS_PUBLIC_KEY, "wb") as f:
                f.write(crypto.dump_publickey(crypto.FILETYPE_PEM, pkey))
    except NamedLock.NotAvailable:
        # System is running a region and rack. The other process
        # is generating the key, wait up to 60s for it.
        waits = 0
        while not os.path.isfile(MAAS_PRIVATE_KEY) and waits < 600:
            sleep(0.1)
            waits += 1
        assert os.path.isfile(
            MAAS_PRIVATE_KEY
        ), "Unable to generate MAAS RSA keys!"
    return True


def generate_certificate_if_needed(
    not_before=0, not_after=(60 * 60 * 24 * 365)
):
    """Generate RSA keys and certificate if needed.

    Returns True if a new certificate was generated.
    """
    generate_rsa_keys_if_needed()
    if os.path.isfile(MAAS_CERTIFICATE):
        # Certificate exists, check if its still valid.
        with open(MAAS_CERTIFICATE, "rb") as f:
            cert = crypto.load_certificate(crypto.FILETYPE_PEM, f.read())
        now = datetime.utcnow()
        cert_not_before = datetime.strptime(
            cert.get_notBefore().decode(), "%Y%m%d%H%M%SZ"
        )
        cert_not_after = datetime.strptime(
            cert.get_notAfter().decode(), "%Y%m%d%H%M%SZ"
        )
        needs_certificate = (now < cert_not_before) or (now > cert_not_after)
    else:
        needs_certificate = True

    if not needs_certificate:
        return False

    try:
        with NamedLock("certificate"):
            with open(MAAS_PRIVATE_KEY, "rb") as f:
                pkey = crypto.load_privatekey(crypto.FILETYPE_PEM, f.read())

            cert_req = crypto.X509Req()
            cert_req.get_subject().CN = gethostname()
            cert_req.set_pubkey(pkey)
            cert_req.sign(pkey, "sha512")

            cert = crypto.X509()
            cert.get_subject().CN = cert_req.get_subject().CN
            cert.gmtime_adj_notBefore(not_before)
            cert.gmtime_adj_notAfter(not_after)
            cert.set_pubkey(cert_req.get_pubkey())
            cert.sign(pkey, "sha512")

            if os.path.exists(MAAS_CERTIFICATE):
                os.remove(MAAS_CERTIFICATE)
            with open(MAAS_CERTIFICATE, "wb") as f:
                f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
    except NamedLock.NotAvailable:
        # System is running a region and rack. The other process
        # is generating the certificate, wait up to 60s for it.
        waits = 0
        while not os.path.isfile(MAAS_CERTIFICATE) and waits < 600:
            sleep(0.1)
            waits += 1
        assert os.path.isfile(
            MAAS_CERTIFICATE
        ), "Unable to generate MAAS certificate!"
    return True


def get_certificate_fingerprint(digest_name="sha256"):
    """Return the fingerprint of the current certificate."""
    with open(MAAS_CERTIFICATE, "rb") as f:
        cert = crypto.load_certificate(crypto.FILETYPE_PEM, f.read())
    return cert.digest(digest_name).decode()
