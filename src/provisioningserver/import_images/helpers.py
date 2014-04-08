# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Miscellaneous small definitions in support of boot-resource import."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'get_signing_policy',
    'ImageSpec',
    'logger',
    ]

from collections import namedtuple
import functools
import logging

from simplestreams.util import policy_read_signed

# A tuple of the items that together select a boot image.
ImageSpec = namedtuple(b'ImageSpec', [
    'arch',
    'subarch',
    'release',
    'label',
    ])


def get_signing_policy(path, keyring=None):
    """Return Simplestreams signing policy for the given path.

    :param path: Path to the Simplestreams index file.
    :param keyring: Optional keyring file for verifying signatures.
    :return: A "signing policy" callable.  It accepts a file's content, path,
        and optional keyring as arguments, and if the signature verifies
        correctly, returns the content.  The keyring defaults to the one you
        pass.
    """
    if path.endswith('.json'):
        # The configuration deliberately selected an un-signed index.  A signed
        # index would have a suffix of '.sjson'.  Use a policy that doesn't
        # check anything.
        policy = lambda content, path, keyring: content
    else:
        # Otherwise: use default Simplestreams policy for verifying signatures.
        policy = policy_read_signed

    if keyring is not None:
        # Pass keyring to the policy, to use if the caller inside Simplestreams
        # does not provide one.
        policy = functools.partial(policy, keyring=keyring)

    return policy


def init_logger(log_level=logging.INFO):
    logger = logging.getLogger(__name__)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(log_level)
    return logger


logger = init_logger()
