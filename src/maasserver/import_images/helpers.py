# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Miscellaneous small definitions in support of boot-resource import."""

from collections import namedtuple
import functools

from simplestreams.util import policy_read_signed

from provisioningserver.logger import get_maas_logger

# A tuple of the items that together select a boot image.
ImageSpec = namedtuple(
    "ImageSpec", ["os", "arch", "subarch", "kflavor", "release", "label"]
)


def get_signing_policy(path, keyring=None):
    """Return Simplestreams signing policy for the given path.

    :param path: Path to the Simplestreams index file.
    :param keyring: Optional keyring file for verifying signatures.
    :return: A "signing policy" callable.  It accepts a file's content, path,
        and optional keyring as arguments, and if the signature verifies
        correctly, returns the content.  The keyring defaults to the one you
        pass.
    """
    if path.endswith(".json"):
        # The configuration deliberately selected an un-signed index.  A signed
        # index would have a suffix of '.sjson'.  Use a policy that doesn't
        # check anything.

        def policy(content, path, keyring):
            return content

    else:
        # Otherwise: use default Simplestreams policy for verifying signatures.
        policy = policy_read_signed

    if keyring is not None:
        # Pass keyring to the policy, to use if the caller inside Simplestreams
        # does not provide one.
        policy = functools.partial(policy, keyring=keyring)

    return policy


def get_os_from_product(item):
    """Returns the operating system that the product is refering to.

    Originally products did not contain the os field. This handles that missing
    field, by returning "ubuntu" as the operating system. Before the os field
    was added to the product mapping, only Ubuntu was supported.
    """
    try:
        return item["os"]
    except KeyError:
        return "ubuntu"


maaslog = get_maas_logger("import-images")
