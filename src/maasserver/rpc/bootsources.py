# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to boot sources."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "get_boot_sources",
]

from base64 import b64decode

from maasserver.models import BootSource
from maasserver.utils.async import transactional
from provisioningserver.utils.twisted import synchronous


@synchronous
@transactional
def get_boot_sources(uuid, remove_os=False):
    """Obtain boot sources and selections from the database.

    Returns them as a structure suitable for returning in the response
    for :py:class:`~provisioningserver.rpc.region.GetBootSources`.

    :param remove_os: Remove the os field from selections. This is
        used for v1 of get_boot_sources, as it should not include the os field.
        For v2 of get_boot_sources, the os field is included.
    """
    # No longer is uuid used for this, as its now global. The uuid is just
    # ignored.
    sources = [
        source.to_dict()
        for source in BootSource.objects.all()
    ]
    # Replace the keyring_data value (base-64 encoded keyring) with
    # the raw bytes; AMP is fine with bytes.
    for source in sources:
        keyring_data = source.pop("keyring_data")
        source["keyring_data"] = b64decode(keyring_data)
        if remove_os:
            for selection in source['selections']:
                del selection['os']
    return sources
