# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Security-related code, primarily relating to TLS."""


from datetime import datetime
import os

from pytz import UTC

from maasserver import locks
from maasserver.secrets import SecretManager, SecretNotFound
from maasserver.utils import synchronised
from maasserver.utils.orm import transactional, with_connection
from maasserver.utils.threads import deferToDatabase
from provisioningserver.security import (
    get_shared_secret_from_filesystem,
    set_shared_secret_on_filesystem,
    to_bin,
    to_hex,
)
from provisioningserver.utils.env import MAAS_SHARED_SECRET
from provisioningserver.utils.twisted import asynchronous, synchronous


def get_serial():
    ref = datetime(2012, 1, 16, tzinfo=UTC)
    now = datetime.now(tz=UTC)
    serial = (now - ref).total_seconds()
    return int(serial)


@synchronous
@with_connection  # Needed by the following lock.
@synchronised(locks.security)  # Region-wide lock.
@transactional
def get_shared_secret_txn():
    manager = SecretManager()
    try:
        secret_in_db_hex = manager.get_simple_secret("rpc-shared")
        secret_in_db = to_bin(secret_in_db_hex) if secret_in_db_hex else None
    except SecretNotFound:
        secret_in_db = None
    # Load secret from the filesystem, if it exists.
    secret_on_fs = get_shared_secret_from_filesystem()

    if secret_in_db is None and secret_on_fs is None:
        secret = os.urandom(16)  # 16-bytes of crypto-standard noise.
        manager.set_simple_secret("rpc-shared", to_hex(secret))
        set_shared_secret_on_filesystem(secret)
    elif secret_in_db is None:
        secret = secret_on_fs
        manager.set_simple_secret("rpc-shared", to_hex(secret))
    elif secret_on_fs is None:
        secret = secret_in_db
        set_shared_secret_on_filesystem(secret)
    elif secret_in_db == secret_on_fs:
        secret = secret_in_db  # or secret_on_fs.
    else:
        raise AssertionError(
            "The secret stored in the database does not match the secret "
            f"stored on the filesystem at {MAAS_SHARED_SECRET.path}. Please investigate."
        )

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
