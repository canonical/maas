# Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The SSHKey handler for the WebSocket connection."""


from django.core.exceptions import ValidationError
from django.http import HttpRequest

from maasserver.audit import create_audit_event
from maasserver.enum import ENDPOINT
from maasserver.forms import SSHKeyForm
from maasserver.models.keysource import KeySource
from maasserver.models.sshkey import SSHKey
from maasserver.utils.keys import ImportSSHKeysError
from maasserver.websockets.base import HandlerError, HandlerValidationError
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)
from provisioningserver.events import EVENT_TYPES


class SSHKeyHandler(TimestampedModelHandler):
    class Meta:
        queryset = SSHKey.objects.all()
        allowed_methods = ["list", "get", "create", "delete", "import_keys"]
        listen_channels = ["sshkey"]

    def get_queryset(self, for_list=False):
        """Return `QuerySet` for SSH keys owned by `user`."""
        return self._meta.queryset.filter(user=self.user)

    def get_object(self, params, permission=None):
        """Only allow getting keys owned by the user."""
        return super().get_own_object(params, permission=permission)

    def dehydrate_keysource(self, keysource):
        """Dehydrate the keysource to include protocol and auth_id."""
        if keysource is None:
            return None
        else:
            return {
                "protocol": keysource.protocol,
                "auth_id": keysource.auth_id,
            }

    def dehydrate(self, obj, data, for_list=False):
        """Add display to the SSH key."""
        data["display"] = obj.display_html(70)
        return data

    def create(self, params):
        """Create a SSHKey."""
        form = SSHKeyForm(user=self.user, data=params)
        if form.is_valid():
            try:
                request = HttpRequest()
                request.user = self.user
                request.data = params
                obj = form.save(ENDPOINT.UI, request)
            except ValidationError as e:
                try:
                    raise HandlerValidationError(e.message_dict)
                except AttributeError:
                    raise HandlerValidationError({"__all__": e.message})
            return self.full_dehydrate(obj)
        else:
            raise HandlerValidationError(form.errors)

    def import_keys(self, params):
        """Import the requesting user's SSH keys.

        Import SSH keys for a given protocol and authorization ID in
        protocol:auth_id format.
        """
        try:
            KeySource.objects.save_keys_for_user(
                user=self.user,
                protocol=params["protocol"],
                auth_id=params["auth_id"],
            )
            request = HttpRequest()
            request.user = self.user
            create_audit_event(
                EVENT_TYPES.AUTHORISATION,
                ENDPOINT.UI,
                request,
                None,
                description="Imported SSH keys.",
            )
        except ImportSSHKeysError as e:
            raise HandlerError(str(e))
