# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `SSLKey`."""

import http.client

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from piston3.emitters import JSONEmitter
from piston3.handler import typemapper
from piston3.utils import rc

from maasserver.api.support import OperationsHandler
from maasserver.audit import create_audit_event
from maasserver.enum import ENDPOINT
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms import SSLKeyForm
from maasserver.models import SSLKey
from provisioningserver.events import EVENT_TYPES

DISPLAY_SSLKEY_FIELDS = ("id", "key")


class SSLKeysHandler(OperationsHandler):
    """Operations on multiple keys."""

    api_doc_section_name = "SSL Keys"

    update = delete = None

    def read(self, request):
        """@description-title List keys
        @description List all keys belonging to the requesting user.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing a list of SSL
        keys.
        @success-example "success-json" [exkey=ssl-keys-list] placeholder text
        """
        return SSLKey.objects.filter(user=request.user).order_by("id")

    def create(self, request):
        """@description-title Add a new SSL key
        @description Add a new SSL key to the requesting user's account.

        @param (string) "key" [required=true,formatting=true] An SSL key
        should be provided in the request payload as form data with the name
        'key':

        ``key: "key data"``

        - ``key data``: The contents of a pem file.

        @success (http-status-code) "201" 201
        @success (json) "success-json" A JSON object containing the new key.
        @success-example "success-json" [exkey=ssl-keys-create] placeholder
        text
        """
        form = SSLKeyForm(user=request.user, data=request.data)
        if form.is_valid():
            sslkey = form.save(ENDPOINT.API, request)
            emitter = JSONEmitter(
                sslkey, typemapper, None, DISPLAY_SSLKEY_FIELDS
            )
            stream = emitter.render(request)
            return HttpResponse(
                stream,
                content_type="application/json; charset=utf-8",
                status=int(http.client.CREATED),
            )
        else:
            raise MAASAPIValidationError(form.errors)

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("sslkeys_handler", [])


class SSLKeyHandler(OperationsHandler):
    """
    Manage an SSL key.

    SSL keys can be retrieved or deleted.
    """

    api_doc_section_name = "SSL Key"

    fields = DISPLAY_SSLKEY_FIELDS
    model = SSLKey
    create = update = None

    def read(self, request, id):
        """@description-title Retrieve an SSL key
        @description Retrieves an SSL key with the given ID.

        @param (int) "id" [required=true] An SSL key ID.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing a list of
        imported keys.
        @success-example "success-json" [exkey=ssl-keys-get] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested SSH key is not found.
        @error-example "not-found"
            No SSLKey matches the given query.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The requesting user does not own the key.
        @error-example "no-perms"
            Can't get a key you don't own.
        """
        key = get_object_or_404(SSLKey, id=id)
        if key.user != request.user:
            return HttpResponseForbidden("Can't get a key you don't own.")
        return key

    def delete(self, request, id):
        """@description-title Delete an SSL key
        @description Deletes the SSL key with the given ID.

        @param (int) "id" [required=true] An SSH key ID.

        @success (http-status-code) "204" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested SSH key is not found.
        @error-example "not-found"
            No SSLKey matches the given query.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The requesting user does not own the key.
        @error-example "no-perms"
            Can't delete a key you don't own.
        """
        key = get_object_or_404(SSLKey, id=id)
        if key.user != request.user:
            return HttpResponseForbidden(
                "Can't delete a key you don't own.",
                content_type=(
                    "text/plain; charset=%s" % settings.DEFAULT_CHARSET
                ),
            )
        key.delete()
        create_audit_event(
            EVENT_TYPES.AUTHORISATION,
            ENDPOINT.API,
            request,
            None,
            description="Deleted SSL key id='%s'." % id,
        )
        return rc.DELETED

    @classmethod
    def resource_uri(cls, sslkey=None):
        keyid = "id"
        if sslkey is not None:
            keyid = sslkey.id
        return ("sslkey_handler", (keyid,))
