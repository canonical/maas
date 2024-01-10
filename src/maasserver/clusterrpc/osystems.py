# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Obtain OS information from clusters."""

__all__ = [
    "validate_license_key",
]

from functools import partial

from twisted.python.failure import Failure

from maasserver.rpc import getAllClients
from maasserver.utils import asynchronous
from provisioningserver.rpc.cluster import ValidateLicenseKey
from provisioningserver.utils.twisted import synchronous


def suppress_failures(responses):
    """Suppress failures returning from an async/gather operation.

    This may not be advisable! Be very sure this is what you want.
    """
    for response in responses:
        if not isinstance(response, Failure):
            yield response


@synchronous
def validate_license_key(osystem, release, key):
    """Validate license key for the given OS and release.

    Checks all rack controllers to determine if the license key is valid. Only
    one rack controller has to say the license key is valid.

    :param osystem: The name of the operating system.
    :param release: The release for the operating system.
    :param key: The license key to validate.

    :return: True if valid, False otherwise.
    """
    responses = asynchronous.gather(
        partial(
            client,
            ValidateLicenseKey,
            osystem=osystem,
            release=release,
            key=key,
        )
        for client in getAllClients()
    )

    # Only one cluster needs to say the license key is valid, for it
    # to considered valid. Must go through all responses so they are all
    # marked handled.
    is_valid = False
    for response in suppress_failures(responses):
        is_valid = is_valid or response["is_valid"]
    return is_valid
