# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `BlockDevice`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type

from django.shortcuts import get_object_or_404
from maasserver.api.support import (
    admin_method,
    operation,
    OperationsHandler,
)
from maasserver.api.utils import get_mandatory_param
from maasserver.models import BlockDevice


DISPLAYED_BLOCKDEVICE_FIELDS = (
    'id',
    'name',
    'path',
    'id_path',
    'size',
    'block_size',
    'tags',
)


class BlockDeviceHandler(OperationsHandler):
    """Manage a BlockDevice.

    The device is identified by its database id.
    """
    api_doc_section_name = "BlockDevice"
    create = replace = update = read = None
    model = BlockDevice
    fields = DISPLAYED_BLOCKDEVICE_FIELDS

    @admin_method
    @operation(idempotent=True)
    def add_tag(self, request, device_id):
        """Add a tag to a BlockDevice.

        :param tag: The tag being added.
        """
        device = get_object_or_404(BlockDevice, id=device_id)
        device.add_tag(get_mandatory_param(request.GET, 'tag'))
        device.save()
        return device

    @admin_method
    @operation(idempotent=True)
    def remove_tag(self, request, device_id):
        """Remove a tag from a BlockDevice.

        :param tag: The tag being removed.
        """
        device = get_object_or_404(BlockDevice, id=device_id)
        device.remove_tag(get_mandatory_param(request.GET, 'tag'))
        device.save()
        return device
