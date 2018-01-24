# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handler: `Account`."""

__all__ = [
    'AccountHandler',
]

import http.client
import json

from django.http import HttpResponse
from maasserver.api.support import (
    operation,
    OperationsHandler,
)
from maasserver.api.utils import (
    get_mandatory_param,
    get_optional_param,
)
from maasserver.audit import create_audit_event
from maasserver.enum import ENDPOINT
from piston3.utils import rc
from provisioningserver.events import EVENT_TYPES


def _format_tokens(tokens):
    """Converts the given tokens into a list of dictionaries to represent them.

    :param tokens: The result of `profile.get_authorisation_tokens()`.
    """
    return [
        {
            "name": token.consumer.name,
            "token": ":".join([token.consumer.key, token.key, token.secret])
        }
        for token in tokens
    ]


class AccountHandler(OperationsHandler):
    """Manage the current logged-in user."""
    api_doc_section_name = "Logged-in user"
    create = read = update = delete = None

    @operation(idempotent=False)
    def create_authorisation_token(self, request):
        """Create an authorisation OAuth token and OAuth consumer.

        :param name: Optional name of the token that will be generated.
        :type name: unicode
        :return: a json dict with four keys: 'token_key',
            'token_secret', 'consumer_key'  and 'name'(e.g.
            {token_key: 's65244576fgqs', token_secret: 'qsdfdhv34',
            consumer_key: '68543fhj854fg', name: 'MAAS consumer'}).
        :rtype: string (json)

        """
        profile = request.user.userprofile
        consumer_name = get_optional_param(request.data, 'name')
        consumer, token = profile.create_authorisation_token(consumer_name)
        create_audit_event(
            EVENT_TYPES.AUTHORISATION, ENDPOINT.API,
            request, None, "Created token for '%(username)s'.")
        auth_info = {
            'token_key': token.key, 'token_secret': token.secret,
            'consumer_key': consumer.key, 'name': consumer.name
        }
        return HttpResponse(
            json.dumps(auth_info),
            content_type='application/json; charset=utf-8',
            status=int(http.client.OK))

    @operation(idempotent=False)
    def delete_authorisation_token(self, request):
        """Delete an authorisation OAuth token and the related OAuth consumer.

        :param token_key: The key of the token to be deleted.
        :type token_key: unicode
        """
        profile = request.user.userprofile
        token_key = get_mandatory_param(request.data, 'token_key')
        profile.delete_authorisation_token(token_key)
        create_audit_event(
            EVENT_TYPES.AUTHORISATION, ENDPOINT.API,
            request, None, "Deleted token for '%(username)s'.")
        return rc.DELETED

    @operation(idempotent=False)
    def update_token_name(self, request):
        """Modify the consumer name of an authorisation OAuth token.

        :param token: Can be the whole token or only the token key.
        :type token: unicode
        :param name: New name of the token.
        :type name: unicode
        """
        profile = request.user.userprofile
        token = get_mandatory_param(request.data, 'token')
        token_fields = token.split(":")
        if len(token_fields) == 3:
            token_key = token_fields[1]
        else:
            token_key = token
        consumer_name = get_mandatory_param(request.data, 'name')
        profile.modify_consumer_name(token_key, consumer_name)
        create_audit_event(
            EVENT_TYPES.AUTHORISATION, ENDPOINT.API, request,
            None, "Modified consumer name of token for '%(username)s'.")
        return rc.ACCEPTED

    @operation(idempotent=True)
    def list_authorisation_tokens(self, request):
        """List authorisation tokens available to the currently logged-in user.

        :return: list of dictionaries representing each key's name and token.
        """
        profile = request.user.userprofile
        tokens = _format_tokens(profile.get_authorisation_tokens())
        return HttpResponse(
            json.dumps(tokens, indent=4),
            content_type='application/json; charset=utf-8',
            status=int(http.client.OK))

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('account_handler', [])
