# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The Token handler for the WebSocket connection."""

from django.http import HttpRequest
from piston3.models import Token

from maasserver.audit import create_audit_event
from maasserver.enum import ENDPOINT
from maasserver.models.user import create_auth_token, get_auth_tokens
from maasserver.websockets.base import Handler
from provisioningserver.events import EVENT_TYPES


class TokenHandler(Handler):
    class Meta:
        queryset = Token.objects.none()  # Overridden in `get_querset`.
        allowed_methods = ["list", "get", "create", "update", "delete"]
        listen_channels = ["token"]

    def get_queryset(self, for_list=False):
        """Return `QuerySet` for `Token` owned by `user`."""
        return get_auth_tokens(self.user)

    def get_object(self, params, permission=None):
        return super().get_own_object(params, permission=permission)

    def full_dehydrate(self, obj, for_list=False):
        """Return the representation for the object."""
        return {
            "id": obj.id,
            "key": obj.key,
            "secret": obj.secret,
            "consumer": {"key": obj.consumer.key, "name": obj.consumer.name},
        }

    def create(self, params):
        """Create a Token."""
        token = create_auth_token(self.user, params.get("name"))
        request = HttpRequest()
        request.user = self.user
        create_audit_event(
            EVENT_TYPES.AUTHORISATION,
            ENDPOINT.UI,
            request,
            None,
            "Created token.",
        )
        return self.full_dehydrate(token)

    def update(self, params):
        """Update a Token.

        Only the name can be updated.
        """
        token = self.get_object(params)
        name = params.get("name")
        if name != token.consumer.name:
            token.consumer.name = params.get("name")
            token.consumer.save()
            request = HttpRequest()
            request.user = self.user
            create_audit_event(
                EVENT_TYPES.AUTHORISATION,
                ENDPOINT.UI,
                request,
                None,
                "Modified consumer name of token.",
            )
        return self.full_dehydrate(token)
