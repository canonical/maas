# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Security-related code, primarily relating to TLS."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "get_region_certificate",
]

from datetime import datetime

from maasserver import locks
from maasserver.models.config import Config
from provisioningserver.utils import synchronous
from pytz import UTC
from twisted.internet import ssl


def get_serial():
    ref = datetime(2012, 01, 16, tzinfo=UTC)
    now = datetime.now(tz=UTC)
    serial = (now - ref).total_seconds()
    return int(serial)


def load_region_certificate():
    upem = Config.objects.get_config("rpc_region_certificate")
    if upem is None:
        return None
    else:
        # The certificate will be returned as a unicode string. However,
        # it's in PEM form, a base-64 encoded certificate and key, so we
        # need to get back to bytes, then parse it.
        pem = upem.decode("ascii")
        return ssl.PrivateCertificate.loadPEM(pem)


def save_region_certificate(cert):
    assert isinstance(cert, ssl.PrivateCertificate)
    # We'll store the PEM dump of the certificate in the database. We'll
    # get this as a byte-string, so we need to decode to unicode.
    upem = cert.dumpPEM().decode("ascii")
    Config.objects.set_config("rpc_region_certificate", upem)


def generate_region_certificate():
    key = ssl.KeyPair.generate(size=2048)
    return key.selfSignedCert(serialNumber=get_serial(), CN="MAAS Region")


@synchronous
def get_region_certificate():
    cert = load_region_certificate()
    if cert is None:
        with locks.security:
            # Load again, while holding the security lock.
            cert = load_region_certificate()
            if cert is None:
                cert = generate_region_certificate()
                save_region_certificate(cert)
    return cert
