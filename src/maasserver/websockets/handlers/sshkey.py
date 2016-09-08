# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The SSHKey handler for the WebSocket connection."""

__all__ = [
    "SSHKeyHandler",
    ]

from maasserver.models.sshkey import SSHKey
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class SSHKeyHandler(TimestampedModelHandler):

    class Meta:
        queryset = SSHKey.objects.all()
        allowed_methods = [
            'list',
            'get',
            'create',
            'delete',
        ]
        listen_channels = [
            "sshkey",
        ]

    def get_queryset(self):
        """Return `QuerySet` for SSH keys owned by `user`."""
        return self._meta.queryset.filter(user=self.user)
