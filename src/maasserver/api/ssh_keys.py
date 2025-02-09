# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `SSHKey`."""

import http.client

from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.urls import reverse
from piston3.emitters import JSONEmitter
from piston3.handler import typemapper
from piston3.utils import rc
from requests.exceptions import RequestException

from maasserver.api.support import operation, OperationsHandler
from maasserver.api.utils import get_optional_param
from maasserver.audit import create_audit_event
from maasserver.enum import ENDPOINT, KEYS_PROTOCOL_TYPE
from maasserver.exceptions import MAASAPIBadRequest, MAASAPIValidationError
from maasserver.forms import SSHKeyForm
from maasserver.models import SSHKey
from maasserver.models.sshkey import ImportSSHKeysError
from maasserver.utils.orm import get_one
from provisioningserver.events import EVENT_TYPES

DISPLAY_SSHKEY_FIELDS = ("id", "key", "keysource")


class SSHKeysHandler(OperationsHandler):
    """Manage the collection of all the SSH keys in this MAAS."""

    api_doc_section_name = "SSH Keys"

    update = delete = None

    def read(self, request):
        """@description-title List SSH keys
        @description List all keys belonging to the requesting user.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing a list of
        available SSH keys.
        @success-example "success-json" [exkey=ssh-keys-list] placeholder text
        """
        return SSHKey.objects.filter(user=request.user)

    def create(self, request):
        """@description-title Add a new SSH key
        @description Add a new SSH key to the requesting or supplied user's
        account.

        @param (string) "key" [required=true,formatting=true] A public SSH key
        should be provided in the request payload as form data with the name
        'key':

        ``key: "key-type public-key-data"``

        - ``key-type``: ecdsa-sha2-nistp256, ecdsa-sha2-nistp384,
          ecdsa-sha2-nistp521, ssh-dss, ssh-ed25519, ssh-rsa
        - ``public key data``: Base64-encoded key data.

        @success (http-status-code) "201" 201
        @success (json) "success-json" A JSON object containing the new key.
        @success-example "success-json" [exkey=ssh-keys-create] placeholder
        text
        """
        user = request.user
        username = get_optional_param(request.POST, "user")
        if username is not None and request.user.is_superuser:
            supplied_user = get_one(User.objects.filter(username=username))
            if supplied_user is not None:
                user = supplied_user
            else:
                # Raise an error so that the user can know that their
                # attempt at specifying a user did not work.
                raise MAASAPIValidationError(
                    "Supplied username does not match any current users."
                )
        elif username is not None and not request.user.is_superuser:
            raise MAASAPIValidationError(
                "Only administrators can specify a user"
                " when creating an SSH key."
            )

        form = SSHKeyForm(user=user, data=request.data)
        if form.is_valid():
            sshkey = form.save(ENDPOINT.API, request)
            emitter = JSONEmitter(
                sshkey, typemapper, None, DISPLAY_SSHKEY_FIELDS
            )
            stream = emitter.render(request)
            return HttpResponse(
                stream,
                content_type="application/json; charset=utf-8",
                status=int(http.client.CREATED),
            )
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False, exported_as="import")
    def import_ssh_keys(self, request):
        """@description-title Import SSH keys
        @description Import the requesting user's SSH keys for a given protocol
        and authorization ID in protocol:auth_id format.

        @param (string) "keysource" [required=true,formatting=true] The source
        of the keys to import should be provided in the request payload as form
        data:

        E.g.

        ``source:user``

        - ``source``: lp (Launchpad), gh (GitHub)
        - ``user``: User login

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing a list of
        imported keys.
        @success-example "success-json" [exkey=ssh-keys-import] placeholder
        text
        """
        keysource = request.data.get("keysource", None)
        if keysource is not None:
            if ":" in keysource:
                protocol, auth_id = keysource.split(":", 1)
            else:
                protocol = KEYS_PROTOCOL_TYPE.LP
                auth_id = keysource
            try:
                keysource = SSHKey.objects.from_keysource(
                    user=request.user, protocol=protocol, auth_id=auth_id
                )
                create_audit_event(
                    EVENT_TYPES.AUTHORISATION,
                    ENDPOINT.API,
                    request,
                    None,
                    description="Imported SSH keys.",
                )
                # convert to response
                return [
                    {
                        "id": sshkey.id,
                        "key": sshkey.key,
                        "keysource": f"{sshkey.protocol}:{sshkey.auth_id}",
                        "resource_uri": reverse(
                            "sshkey_handler", kwargs={"id": sshkey.id}
                        ),
                    }
                    for sshkey in keysource
                ]
            except (ImportSSHKeysError, RequestException) as e:
                raise MAASAPIBadRequest(e.args[0])  # noqa: B904
        else:
            raise MAASAPIBadRequest(
                "Importing SSH keys failed. "
                "Input needs to be in protocol:auth_id or auth_id format."
            )

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("sshkeys_handler", [])


class SSHKeyHandler(OperationsHandler):
    """
    Manage an SSH key.

    SSH keys can be retrieved or deleted.
    """

    api_doc_section_name = "SSH Key"

    fields = DISPLAY_SSHKEY_FIELDS
    model = SSHKey
    create = update = None

    def read(self, request, id):
        """@description-title Retrieve an SSH key
        @description Retrieves an SSH key with the given ID.

        @param (int) "id" [required=true] An SSH key ID.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing a list of
        imported keys.
        @success-example "success-json" [exkey=ssh-keys-get] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested SSH key is not found.
        @error-example "not-found"
            No SSHKey matches the given query.
        """
        key = get_object_or_404(SSHKey, id=id)
        return key

    def delete(self, request, id):
        """@description-title Delete an SSH key
        @description Deletes the SSH key with the given ID.

        @param (int) "id" [required=true] An SSH key ID.

        @success (http-status-code) "204" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested SSH key is not found.
        @error-example "not-found"
            No SSHKey matches the given query.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The requesting user does not own the key.
        @error-example "no-perms"
            Can't delete a key you don't own.
        """
        key = get_object_or_404(SSHKey, id=id)
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
            description="Deleted SSH key id='%s'." % id,
        )
        return rc.DELETED

    @classmethod
    def keysource(cls, sshkey):
        keysource = ""
        if sshkey.protocol is not None and sshkey.auth_id is not None:
            keysource = f"{sshkey.protocol}:{sshkey.auth_id}"
        return keysource

    @classmethod
    def resource_uri(cls, sshkey=None):
        keyid = "id"
        if sshkey is not None:
            keyid = sshkey.id
        return ("sshkey_handler", (keyid,))
