# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The DHCPSnippet handler for the WebSocket connection."""

__all__ = [
    "DHCPSnippetHandler",
    ]

from email.utils import format_datetime

from maasserver.forms.dhcpsnippet import DHCPSnippetForm
from maasserver.models import DHCPSnippet
from maasserver.utils.orm import reload_object
from maasserver.websockets.base import (
    HandlerPermissionError,
    HandlerValidationError,
)
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class DHCPSnippetHandler(TimestampedModelHandler):

    class Meta:
        queryset = DHCPSnippet.objects.all().select_related('value', 'node')
        pk = 'id'
        allowed_methods = [
            'list',
            'get',
            'create',
            'update',
            'delete',
            'revert',
        ]
        listen_channels = ['dhcpsnippet']
        form = DHCPSnippetForm

    def dehydrate_node(self, node):
        """Return the node system_id instead of the id."""
        if node is not None:
            return node.system_id
        else:
            return None

    def dehydrate_value(self, value):
        """Return the real value instead of the object relation."""
        return value.data

    def dehydrate(self, obj, data, for_list=False):
        """Add DHCPSnippet value history to `data`."""
        data['history'] = [
            {
                'id': value.id,
                'value': value.data,
                'created': format_datetime(value.created),
            }
            for value in obj.value.previous_versions()
        ]
        return data

    def create(self, params):
        """Create the object from params iff admin."""
        if not reload_object(self.user).is_superuser:
            raise HandlerPermissionError()
        return super().create(params)

    def update(self, params):
        """Update the object from params iff admin."""
        if not reload_object(self.user).is_superuser:
            raise HandlerPermissionError()
        return super().update(params)

    def delete(self, params):
        """Delete the object from params iff admin."""
        if not reload_object(self.user).is_superuser:
            raise HandlerPermissionError()
        return super().delete(params)

    def revert(self, params):
        """Revert a value to a previous state."""
        if not reload_object(self.user).is_superuser:
            raise HandlerPermissionError()

        dhcp_snippet = self.get_object(params)
        revert_to = params.get('to')
        if revert_to is None:
            raise HandlerValidationError('You must specify where to revert to')
        try:
            revert_to = int(revert_to)
        except ValueError:
            raise HandlerValidationError(
                "%s is an invalid 'to' value" % revert_to)
        try:
            def gc_hook(value):
                dhcp_snippet.value = value
                dhcp_snippet.save()
            dhcp_snippet.value.revert(revert_to, gc_hook=gc_hook)
        except ValueError as e:
            raise HandlerValidationError(e.args[0])
