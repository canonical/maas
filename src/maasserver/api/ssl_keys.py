# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `SSLKey`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'SSLKeyHandler',
    'SSLKeysHandler',
    ]

import httplib

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from maasserver.api.support import (
    operation,
    OperationsHandler,
    )
from maasserver.forms import SSLKeyForm
from maasserver.models import SSLKey
from piston.emitters import JSONEmitter
from piston.handler import typemapper
from piston.utils import rc


DISPLAY_SSLKEY_FIELDS = ("id", "key")


class SSLKeysHandler(OperationsHandler):
    """Operations on multiple keys."""
    api_doc_section_name = "SSL Keys"

    create = read = update = delete = None

    @operation(idempotent=True)
    def list(self, request):
        """List all keys belonging to the requesting user."""
        return SSLKey.objects.filter(user=request.user).order_by('id')

    @operation(idempotent=False)
    def new(self, request):
        """Add a new SSL key to the requesting user's account.

        The request payload should contain the SSL key data in form
        data whose name is "key".
        """
        form = SSLKeyForm(user=request.user, data=request.data)
        if form.is_valid():
            sslkey = form.save()
            emitter = JSONEmitter(
                sslkey, typemapper, None, DISPLAY_SSLKEY_FIELDS)
            stream = emitter.render(request)
            return HttpResponse(
                stream, mimetype='application/json; charset=utf-8',
                status=httplib.CREATED)
        else:
            raise ValidationError(form.errors)

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

    def read(self, request, keyid):
        """GET an SSL key."""
        key = get_object_or_404(SSLKey, id=keyid)
        if key.user != request.user:
            return HttpResponse(
                "Can't get a key you don't own.", status=httplib.FORBIDDEN)
        return key

    @operation(idempotent=True)
    def delete(self, request, keyid):
        """DELETE an SSL key."""
        key = get_object_or_404(SSLKey, id=keyid)
        if key.user != request.user:
            return HttpResponse(
                "Can't delete a key you don't own.", status=httplib.FORBIDDEN)
        key.delete()
        return rc.DELETED

    @classmethod
    def resource_uri(cls, sslkey=None):
        keyid = "keyid"
        if sslkey is not None:
            keyid = sslkey.id
        return ('sslkey_handler', (keyid, ))
