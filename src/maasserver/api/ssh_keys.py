# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `SSHKey`."""

__all__ = [
    'SSHKeyHandler',
    'SSHKeysHandler',
    ]

import http.client

from django.conf import settings
from django.http import (
    HttpResponse,
    HttpResponseForbidden,
)
from django.shortcuts import get_object_or_404
from maasserver.api.support import (
    operation,
    OperationsHandler,
)
from maasserver.audit import create_audit_event
from maasserver.enum import (
    ENDPOINT,
    KEYS_PROTOCOL_TYPE,
)
from maasserver.exceptions import (
    MAASAPIBadRequest,
    MAASAPIValidationError,
)
from maasserver.forms import SSHKeyForm
from maasserver.models import (
    KeySource,
    SSHKey,
)
from maasserver.utils.keys import ImportSSHKeysError
from piston3.emitters import JSONEmitter
from piston3.handler import typemapper
from piston3.utils import rc
from provisioningserver.events import EVENT_TYPES
from requests.exceptions import RequestException


DISPLAY_SSHKEY_FIELDS = ("id", "key", "keysource")


class SSHKeysHandler(OperationsHandler):
    """Manage the collection of all the SSH keys in this MAAS."""
    api_doc_section_name = "SSH Keys"

    update = delete = None

    def read(self, request):
        """List all keys belonging to the requesting user."""
        return SSHKey.objects.filter(user=request.user)

    def create(self, request):
        """Add a new SSH key to the requesting user's account.

        The request payload should contain the public SSH key data in form
        data whose name is "key".
        """
        form = SSHKeyForm(user=request.user, data=request.data)
        if form.is_valid():
            sshkey = form.save(ENDPOINT.API, request)
            emitter = JSONEmitter(
                sshkey, typemapper, None, DISPLAY_SSHKEY_FIELDS)
            stream = emitter.render(request)
            return HttpResponse(
                stream, content_type='application/json; charset=utf-8',
                status=int(http.client.CREATED))
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False, exported_as='import')
    def import_ssh_keys(self, request):
        """Import the requesting user's SSH keys.

        Import SSH keys for a given protocol and authorization ID in
        protocol:auth_id format.
        """
        keysource = request.data.get('keysource', None)
        if keysource is not None:
            if ':' in keysource:
                protocol, auth_id = keysource.split(':', 1)
            else:
                protocol = KEYS_PROTOCOL_TYPE.LP
                auth_id = keysource
            try:
                keysource = KeySource.objects.save_keys_for_user(
                    user=request.user, protocol=protocol, auth_id=auth_id)
                create_audit_event(
                    EVENT_TYPES.AUTHORISATION, ENDPOINT.API, request, None,
                    description=("SSH keys imported by '%(username)s'."))
                return keysource
            except (ImportSSHKeysError, RequestException) as e:
                raise MAASAPIBadRequest(e.args[0])
        else:
            raise MAASAPIBadRequest(
                "Importing SSH keys failed. "
                "Input needs to be in protocol:auth_id or auth_id format.")

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('sshkeys_handler', [])


class SSHKeyHandler(OperationsHandler):
    """Manage an SSH key.

    SSH keys can be retrieved or deleted.
    """
    api_doc_section_name = "SSH Key"

    fields = DISPLAY_SSHKEY_FIELDS
    model = SSHKey
    create = update = None

    def read(self, request, id):
        """GET an SSH key.

        Returns 404 if the key does not exist.
        """
        key = get_object_or_404(SSHKey, id=id)
        return key

    def delete(self, request, id):
        """DELETE an SSH key.

        Returns 404 if the key does not exist.
        Returns 401 if the key does not belong to the calling user.
        """
        key = get_object_or_404(SSHKey, id=id)
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
                "SSH key id=%s" % id + " deleted by '%(username)s'."))
        return rc.DELETED

    @classmethod
    def keysource(cls, sshkey):
        keysource = ""
        if sshkey.keysource is not None:
            keysource = str(sshkey.keysource)
        return keysource

    @classmethod
    def resource_uri(cls, sshkey=None):
        keyid = "id"
        if sshkey is not None:
            keyid = sshkey.id
        return ('sshkey_handler', (keyid, ))
