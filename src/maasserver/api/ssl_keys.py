# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `SSLKey`."""

__all__ = [
    'SSLKeyHandler',
    'SSLKeysHandler',
    ]

import http.client

from django.conf import settings
from django.http import (
    HttpResponse,
    HttpResponseForbidden,
)
from django.shortcuts import get_object_or_404
from maasserver.api.support import OperationsHandler
from maasserver.audit import create_audit_event
from maasserver.enum import ENDPOINT
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms import SSLKeyForm
from maasserver.models import SSLKey
from piston3.emitters import JSONEmitter
from piston3.handler import typemapper
from piston3.utils import rc
from provisioningserver.events import EVENT_TYPES


DISPLAY_SSLKEY_FIELDS = ("id", "key")


class SSLKeysHandler(OperationsHandler):
    """Operations on multiple keys."""
    api_doc_section_name = "SSL Keys"

    update = delete = None

    def read(self, request):
        """List all keys belonging to the requesting user."""
        return SSLKey.objects.filter(user=request.user).order_by('id')

    def create(self, request):
        """Add a new SSL key to the requesting user's account.

        The request payload should contain the SSL key data in form
        data whose name is "key".
        """
        form = SSLKeyForm(user=request.user, data=request.data)
        if form.is_valid():
            sslkey = form.save(ENDPOINT.API, request)
            emitter = JSONEmitter(
                sslkey, typemapper, None, DISPLAY_SSLKEY_FIELDS)
            stream = emitter.render(request)
            return HttpResponse(
                stream, content_type='application/json; charset=utf-8',
                status=int(http.client.CREATED))
        else:
            raise MAASAPIValidationError(form.errors)

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('sslkeys_handler', [])


class SSLKeyHandler(OperationsHandler):
    """Manage an SSL key.

    SSL keys can be retrieved or deleted.
    """
    api_doc_section_name = "SSL Key"

    fields = DISPLAY_SSLKEY_FIELDS
    model = SSLKey
    create = update = None

    def read(self, request, id):
        """GET an SSL key.

        Returns 404 if the key with `id` is not found.
        Returns 401 if the key does not belong to the requesting user.
        """
        key = get_object_or_404(SSLKey, id=id)
        if key.user != request.user:
            return HttpResponseForbidden(
                "Can't get a key you don't own.")
        return key

    def delete(self, request, id):
        """DELETE an SSL key.

        Returns 401 if the key does not belong to the requesting user.
        Returns 204 if the key is successfully deleted.
        """
        key = get_object_or_404(SSLKey, id=id)
        if key.user != request.user:
            return HttpResponseForbidden(
                "Can't delete a key you don't own.",
                content_type=(
                    "text/plain; charset=%s" % settings.DEFAULT_CHARSET)
            )
        key.delete()
        create_audit_event(
            EVENT_TYPES.AUTHORISATION, ENDPOINT.API, request, None,
            description=(
                "SSL key id=%s" % id + " deleted by '%(username)s'."))
        return rc.DELETED

    @classmethod
    def resource_uri(cls, sslkey=None):
        keyid = "id"
        if sslkey is not None:
            keyid = sslkey.id
        return ('sslkey_handler', (keyid, ))
