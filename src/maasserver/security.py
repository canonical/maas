# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Security-related code, primarily relating to TLS."""

__all__ = [
    "get_region_certificate",
    "get_shared_secret",
]

from datetime import datetime
import os

from maasserver import locks
from maasserver.models.config import Config
from maasserver.utils import synchronised
from maasserver.utils.orm import (
    transactional,
    with_connection,
)
from maasserver.utils.threads import deferToDatabase
from provisioningserver.security import (
    get_shared_secret_filesystem_path,
    get_shared_secret_from_filesystem,
    set_shared_secret_on_filesystem,
    to_bin,
    to_hex,
)
from provisioningserver.utils.twisted import (
    asynchronous,
    synchronous,
)
from pytz import UTC
from twisted.internet import ssl


def get_serial():
    ref = datetime(2012, 1, 16, tzinfo=UTC)
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
        pem = upem.encode("ascii")
        return ssl.PrivateCertificate.loadPEM(pem)


def save_region_certificate(cert):
    assert isinstance(cert, ssl.PrivateCertificate)
    # We'll store the PEM dump of the certificate in the database. We'll
    # get this as a byte-string, so we need to decode to unicode.
    upem = cert.dumpPEM().decode("ascii")
    Config.objects.set_config("rpc_region_certificate", upem)


def generate_region_certificate():
    key = ssl.KeyPair.generate(size=2048)
    return key.selfSignedCert(serialNumber=get_serial(), CN=b"MAAS Region")


@synchronous
@with_connection  # Needed by the following lock.
@synchronised(locks.security)  # Region-wide lock.
@transactional
def get_region_certificate():
    cert = load_region_certificate()
    if cert is None:
        cert = generate_region_certificate()
        save_region_certificate(cert)
    return cert


@synchronous
@with_connection  # Needed by the following lock.
@synchronised(locks.security)  # Region-wide lock.
@transactional
def get_shared_secret_txn():
    # Load secret from database, if it exists.
    secret_in_db_hex = Config.objects.get_config("rpc_shared_secret")
    if secret_in_db_hex is None:
        secret_in_db = None
    else:
        secret_in_db = to_bin(secret_in_db_hex)
    # Load secret from the filesystem, if it exists.
    secret_on_fs = get_shared_secret_from_filesystem()

    if secret_in_db is None and secret_on_fs is None:
        secret = os.urandom(16)  # 16-bytes of crypto-standard noise.
        Config.objects.set_config("rpc_shared_secret", to_hex(secret))
        set_shared_secret_on_filesystem(secret)
    elif secret_in_db is None:
        secret = secret_on_fs
        Config.objects.set_config("rpc_shared_secret", to_hex(secret))
    elif secret_on_fs is None:
        secret = secret_in_db
        set_shared_secret_on_filesystem(secret)
    elif secret_in_db == secret_on_fs:
        secret = secret_in_db  # or secret_on_fs.
    else:
        raise AssertionError(
            "The secret stored in the database does not match the secret "
            "stored on the filesystem at %s. Please investigate." %
            get_shared_secret_filesystem_path())

    return secret


@asynchronous(timeout=10)
def get_shared_secret():
    """Get the shared-secret.

    It may need to generate a new secret and commit it to the database, hence
    this always runs in a separate transaction in a separate thread.

    If called from the IO thread (a.k.a. the reactor), it will return a
    `Deferred` that'll fire with the secret (a byte string).

    If called from another thread it will return the secret directly, but may
    block for up to 10 seconds. If it times-out, an exception is raised.

    :return: The shared-secret, a short byte string, or a `Deferred` if
        called from the IO/reactor thread.
    :raises crochet.TimeoutError: when it times-out after being called from
        thread other than the IO/reactor thread.
    """
    return deferToDatabase(get_shared_secret_txn)
