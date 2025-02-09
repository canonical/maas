# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handler: `Account`."""

import http.client
import json

from django.http import HttpResponse
from piston3.utils import rc

from maasserver.api.support import operation, OperationsHandler
from maasserver.api.utils import get_mandatory_param, get_optional_param
from maasserver.audit import create_audit_event
from maasserver.enum import ENDPOINT
from provisioningserver.events import EVENT_TYPES


def _format_tokens(tokens):
    """Converts the given tokens into a list of dictionaries to represent them.

    :param tokens: The result of `profile.get_authorisation_tokens()`.
    """
    return [
        {
            "name": token.consumer.name,
            "token": ":".join([token.consumer.key, token.key, token.secret]),
        }
        for token in tokens
    ]


class AccountHandler(OperationsHandler):
    """Manage the current logged-in user."""

    api_doc_section_name = "Logged-in user"
    create = read = update = delete = None

    @operation(idempotent=False)
    def create_authorisation_token(self, request):
        """@description-title Create an authorisation token
        @description Create an authorisation OAuth token and OAuth consumer.

        @param (string) "name" [required=false] Optional name of the token that
        will be generated.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing: ``token_key``,
        ``token_secret``, ``consumer_key``, and ``name``.
        @success-example "success-json" [exkey=account-create-token]
        placeholder text
        """
        profile = request.user.userprofile
        consumer_name = get_optional_param(request.data, "name")
        consumer, token = profile.create_authorisation_token(consumer_name)
        create_audit_event(
            EVENT_TYPES.AUTHORISATION,
            ENDPOINT.API,
            request,
            None,
            "Created token.",
        )
        auth_info = {
            "token_key": token.key,
            "token_secret": token.secret,
            "consumer_key": consumer.key,
            "name": consumer.name,
        }
        return HttpResponse(
            json.dumps(auth_info),
            content_type="application/json; charset=utf-8",
            status=int(http.client.OK),
        )

    @operation(idempotent=False)
    def delete_authorisation_token(self, request):
        """@description-title Delete an authorisation token
        @description Delete an authorisation OAuth token and the related OAuth
        consumer.

        @param (string) "token_key" [required=true] The key of the token to be
        deleted.

        @success (http-status-code) "204" 204
        """
        profile = request.user.userprofile
        token_key = get_mandatory_param(request.data, "token_key")
        profile.delete_authorisation_token(token_key)
        create_audit_event(
            EVENT_TYPES.AUTHORISATION,
            ENDPOINT.API,
            request,
            None,
            "Deleted token.",
        )
        return rc.DELETED

    @operation(idempotent=False)
    def update_token_name(self, request):
        """@description-title Modify authorisation token
        @description Modify the consumer name of an authorisation OAuth token.

        @param (string) "token" [required=true] Can be the whole token or only
        the token key.

        @param (string) "name" [required=true] New name of the token.

        @success (http-status-code) "200" 200
        @success (content) "success"
            Accepted
        """
        profile = request.user.userprofile
        token = get_mandatory_param(request.data, "token")
        token_fields = token.split(":")
        if len(token_fields) == 3:
            token_key = token_fields[1]
        else:
            token_key = token
        consumer_name = get_mandatory_param(request.data, "name")
        profile.modify_consumer_name(token_key, consumer_name)
        create_audit_event(
            EVENT_TYPES.AUTHORISATION,
            ENDPOINT.API,
            request,
            None,
            "Modified consumer name of token.",
        )
        return rc.ACCEPTED

    @operation(idempotent=True)
    def list_authorisation_tokens(self, request):
        """@description-title List authorisation tokens
        @description List authorisation tokens available to the currently
        logged-in user.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing a list of token
        objects.
        @success-example "success-json" [exkey=account-list-tokens]
        placeholder text
        """
        profile = request.user.userprofile
        tokens = _format_tokens(profile.get_authorisation_tokens())
        return HttpResponse(
            json.dumps(tokens, indent=4),
            content_type="application/json; charset=utf-8",
            status=int(http.client.OK),
        )

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("account_handler", [])
