# Copyright 2012-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver API."""


import http.client
from itertools import chain
import random
import string
from unittest.mock import ANY

from django.conf import settings
from django.urls import reverse
from piston3.doc import generate_doc
from requests.exceptions import RequestException

from maasserver import urls_api as urlconf
from maasserver.api import account as account_module
from maasserver.api import machines as machines_module
from maasserver.api.doc import find_api_resources
from maasserver.enum import KEYS_PROTOCOL_TYPE
from maasserver.forms.settings import INVALID_SETTING_MSG_TEMPLATE
from maasserver.models import Config, KeySource
from maasserver.models import keysource as keysource_module
from maasserver.models import SSHKey
from maasserver.models.event import Event
from maasserver.models.user import get_auth_tokens
from maasserver.testing import get_data
from maasserver.testing.api import APITestCase, APITransactionTestCase
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.testing.testclient import (
    MAASSensibleClient,
    MAASSensibleOAuthClient,
)
from maasserver.utils.converters import json_load_bytes
from maasserver.utils.keys import ImportSSHKeysError
from maasserver.utils.orm import get_one
from maastesting.testcase import MAASTestCase
from provisioningserver.events import AUDIT


class TestResourceURIs(MAASTestCase):
    """Tests for `resource_uri` usage in handlers."""

    def test_resource_uri_in_docs_matches_handlers_idea_of_resource_uri(self):
        # Sigh. Piston asks handlers for resource_uri information, but also
        # makes use of Django's URL patterns to figure out resource_uri
        # templates for the documentation. Here we check that they match up.
        formatter = string.Formatter()

        def gen_handlers(resource):
            if resource.anonymous is not None:
                yield resource.anonymous
            if resource.handler is not None:
                yield resource.handler

        handlers = chain.from_iterable(
            map(gen_handlers, find_api_resources(urlconf))
        )

        mismatches = []

        for handler in map(type, handlers):
            if hasattr(handler, "resource_uri"):
                resource_uri_params = handler.resource_uri()[1]
                resource_uri_template = generate_doc(
                    handler
                ).resource_uri_template

                fields_expected = tuple(resource_uri_params)
                fields_observed = tuple(
                    fname
                    for _, fname, _, _ in formatter.parse(
                        resource_uri_template
                    )
                    if fname is not None
                )

                if fields_observed != fields_expected:
                    mismatches.append(
                        (handler, fields_expected, fields_observed)
                    )

        if len(mismatches) != 0:
            messages = (
                "{handler.__module__}.{handler.__name__} has mismatched "
                "fields:\n  expected: {expected}\n  observed: {observed}"
                "".format(
                    handler=handler,
                    expected=" ".join(expected),
                    observed=" ".join(observed),
                )
                for handler, expected, observed in mismatches
            )
            messages = chain(
                messages,
                [
                    "Amend the URL patterns for these handlers/resources so that "
                    "the observed fields match what is expected."
                ],
            )
            self.fail("\n--\n".join(messages))


class TestAuthentication(MAASServerTestCase):
    """Tests for `maasserver.api.auth`."""

    def test_invalid_oauth_request(self):
        # An OAuth-signed request that does not validate is an error.
        user = factory.make_User()
        client = MAASSensibleOAuthClient(user)
        # Delete the user's API keys.
        get_auth_tokens(user).delete()
        response = client.post(reverse("nodes_handler"), {"op": "start"})
        self.assertEqual(response.status_code, http.client.UNAUTHORIZED)
        self.assertIn(b"Invalid access token:", response.content)


class TestXSSBugs(APITestCase.ForUser):
    """Tests for making sure we don't allow cross-site scripting bugs."""

    def test_invalid_signature_response_is_textplain(self):
        response = self.client.get(
            reverse("nodes_handler"),
            {"op": "<script>alert(document.domain)</script>"},
        )
        self.assertIn("text/plain", response.get("Content-Type"))
        self.assertNotIn("text/html", response.get("Content-Type"))


class TestAccountAPI(APITestCase.ForUser):
    clientfactories = {
        "user+pass": MAASSensibleClient,
        "oauth": MAASSensibleOAuthClient,
    }

    def test_handler_path(self):
        self.assertEqual("/MAAS/api/2.0/account/", reverse("account_handler"))

    def test_create_authorisation_token(self):
        # The api operation create_authorisation_token returns a json dict
        # with the consumer_key, the token_key, the token_secret and the
        # consumer_name in it.
        mock_create_audit_event = self.patch(
            account_module, "create_audit_event"
        )
        response = self.client.post(
            reverse("account_handler"), {"op": "create_authorisation_token"}
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            "application/json; charset=utf-8", response["content-type"]
        )
        parsed_result = json_load_bytes(response.content)
        self.assertCountEqual(
            ["consumer_key", "name", "token_key", "token_secret"],
            parsed_result,
        )
        self.assertIsInstance(parsed_result["consumer_key"], str)
        self.assertIsInstance(parsed_result["token_key"], str)
        self.assertIsInstance(parsed_result["token_secret"], str)
        self.assertIsInstance(parsed_result["name"], str)
        mock_create_audit_event.assert_called_once()

    def test_create_authorisation_token_with_token_name(self):
        # The api operation create_authorisation_token can also accept
        # a new name for the generated token.
        mock_create_audit_event = self.patch(
            account_module, "create_audit_event"
        )
        token_name = "Test_Token"
        response = self.client.post(
            reverse("account_handler"),
            {"op": "create_authorisation_token", "name": token_name},
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            "application/json; charset=utf-8", response["content-type"]
        )
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(parsed_result["name"], token_name)
        mock_create_audit_event.assert_called_once()

    def test_delete_authorisation_token_not_found(self):
        # If the provided token_key does not exist (for the currently
        # logged-in user), the api returns a 'Not Found' (404) error.
        mock_create_audit_event = self.patch(
            account_module, "create_audit_event"
        )
        response = self.client.post(
            reverse("account_handler"),
            {"op": "delete_authorisation_token", "token_key": "no-such-token"},
        )

        self.assertEqual(http.client.NOT_FOUND, response.status_code)
        mock_create_audit_event.assert_not_called()

    def test_delete_authorisation_token_bad_request_no_token(self):
        # token_key is a mandatory parameter when calling
        # delete_authorisation_token. It it is not present in the request's
        # parameters, the api returns a 'Bad Request' (400) error.
        mock_create_audit_event = self.patch(
            account_module, "create_audit_event"
        )
        response = self.client.post(
            reverse("account_handler"), {"op": "delete_authorisation_token"}
        )

        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        mock_create_audit_event.assert_not_called()

    def test_update_authorisation_token(self):
        token_name_orig = "Test_Token"
        token_name_updated = "Test_Token update"
        mock_create_audit_event = self.patch(
            account_module, "create_audit_event"
        )
        response_creation = self.client.post(
            reverse("account_handler"),
            {"op": "create_authorisation_token", "name": token_name_orig},
        )
        parsed_creation_response = json_load_bytes(response_creation.content)
        created_token = ":".join(
            [
                parsed_creation_response["consumer_key"],
                parsed_creation_response["token_key"],
                parsed_creation_response["token_secret"],
            ]
        )
        self.client.post(
            reverse("account_handler"),
            {
                "op": "update_token_name",
                "token": created_token,
                "name": token_name_updated,
            },
        )
        response_list = self.client.get(
            reverse("account_handler"), {"op": "list_authorisation_tokens"}
        )
        parsed_list_response = json_load_bytes(response_list.content)
        for token in parsed_list_response:
            if token["token"] == created_token:
                self.assertEqual(token["name"], token_name_updated)
        mock_create_audit_event.assert_has_calls([ANY, ANY])

    def test_update_authorisation_token_with_token_key(self):
        # We use only "token_key" portion of the authorisation token
        # to update the token name.
        token_name_orig = "Test_Token"
        token_name_updated = "Test_Token update"
        mock_create_audit_event = self.patch(
            account_module, "create_audit_event"
        )
        response_creation = self.client.post(
            reverse("account_handler"),
            {"op": "create_authorisation_token", "name": token_name_orig},
        )
        parsed_creation_response = json_load_bytes(response_creation.content)
        created_token = ":".join(
            [
                parsed_creation_response["consumer_key"],
                parsed_creation_response["token_key"],
                parsed_creation_response["token_secret"],
            ]
        )
        self.client.post(
            reverse("account_handler"),
            {
                "op": "update_token_name",
                "token": parsed_creation_response["token_key"],
                "name": token_name_updated,
            },
        )
        response_list = self.client.get(
            reverse("account_handler"), {"op": "list_authorisation_tokens"}
        )
        parsed_list_response = json_load_bytes(response_list.content)
        for token in parsed_list_response:
            if token["token"] == created_token:
                self.assertEqual(token["name"], token_name_updated)
        mock_create_audit_event.assert_has_calls([ANY, ANY])

    def test_update_authorisation_token_name_not_found(self):
        # If the provided token_key does not exist (for the currently
        # logged-in user), the api returns a 'Not Found' (404) error.
        mock_create_audit_event = self.patch(
            account_module, "create_audit_event"
        )
        response = self.client.post(
            reverse("account_handler"),
            {
                "op": "update_token_name",
                "token": "no-such-token",
                "name": "test_name",
            },
        )

        self.assertEqual(http.client.NOT_FOUND, response.status_code)
        mock_create_audit_event.assert_not_called()

    def test_update_authorisation_token_name_bad_request_no_token(self):
        # `token` and `name` are mandatory parameters when calling
        # update_token_name. If it is not present in the request's
        # parameters, the api returns a 'Bad Request' (400) error.
        mock_create_audit_event = self.patch(
            account_module, "create_audit_event"
        )
        response = self.client.post(
            reverse("account_handler"), {"op": "update_token_name"}
        )

        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        mock_create_audit_event.assert_not_called()

    def test_list_tokens(self):
        token1_name = "Test Token 1"
        mock_create_audit_event = self.patch(
            account_module, "create_audit_event"
        )
        response_creation = self.client.post(
            reverse("account_handler"),
            {"op": "create_authorisation_token", "name": token1_name},
        )
        parsed_creation_response = json_load_bytes(response_creation.content)
        response = self.client.get(
            reverse("account_handler"), {"op": "list_authorisation_tokens"}
        )
        parsed_list_response = json_load_bytes(response.content)
        self.assertEqual(len(json_load_bytes(response.content)), 2)
        for token in parsed_list_response:
            if token["name"] == token1_name:
                token_fields = token["token"].split(":")
                self.assertEqual(
                    token_fields[0], parsed_creation_response["consumer_key"]
                )
                self.assertEqual(
                    token_fields[1], parsed_creation_response["token_key"]
                )
                self.assertEqual(
                    token_fields[2], parsed_creation_response["token_secret"]
                )
        mock_create_audit_event.assert_called_once()

    def test_list_tokens_format(self):
        self.client.post(
            reverse("account_handler"), {"op": "create_authorisation_token"}
        )
        response = self.client.get(
            reverse("account_handler"), {"op": "list_authorisation_tokens"}
        )
        parsed_list_response = json_load_bytes(response.content)
        self.assertIsInstance(parsed_list_response, list)
        for token in parsed_list_response:
            self.assertCountEqual(["name", "token"], token)
            self.assertIsInstance(token["name"], str)
            self.assertIsInstance(token["token"], str)


class TestSSHKeyHandlers(APITestCase.ForUser):
    def test_sshkeys_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/account/prefs/sshkeys/", reverse("sshkeys_handler")
        )

    def test_sshkey_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/account/prefs/sshkeys/key/",
            reverse("sshkey_handler", args=["key"]),
        )

    def test_list_works(self):
        _, keys = factory.make_user_with_keys(user=self.user)
        response = self.client.get(reverse("sshkeys_handler"))
        self.assertEqual(http.client.OK, response.status_code, response)
        parsed_result = json_load_bytes(response.content)
        expected_result = [
            dict(
                id=keys[0].id,
                key=keys[0].key,
                keysource=str(keys[0].keysource),
                resource_uri=reverse("sshkey_handler", args=[keys[0].id]),
            ),
            dict(
                id=keys[1].id,
                key=keys[1].key,
                keysource=str(keys[1].keysource),
                resource_uri=reverse("sshkey_handler", args=[keys[1].id]),
            ),
        ]
        self.assertEqual(expected_result, parsed_result)

    def test_get_by_id_works(self):
        _, keys = factory.make_user_with_keys(n_keys=1, user=self.user)
        key = keys[0]
        response = self.client.get(reverse("sshkey_handler", args=[key.id]))
        self.assertEqual(http.client.OK, response.status_code, response)
        parsed_result = json_load_bytes(response.content)
        expected = dict(
            id=key.id,
            key=key.key,
            keysource=str(key.keysource),
            resource_uri=reverse("sshkey_handler", args=[key.id]),
        )
        self.assertEqual(expected, parsed_result)

    def test_delete_by_id_works_and_creates_audit_event(self):
        _, keys = factory.make_user_with_keys(n_keys=2, user=self.user)
        response = self.client.delete(
            reverse("sshkey_handler", args=[keys[0].id])
        )
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response
        )
        keys_after = SSHKey.objects.filter(user=self.user)
        self.assertEqual(1, len(keys_after))
        self.assertEqual(keys[1].id, keys_after[0].id)
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(
            event.description, "Deleted SSH key id='%s'." % keys[0].id
        )

    def test_delete_fails_if_not_your_key(self):
        user, keys = factory.make_user_with_keys(n_keys=1)
        response = self.client.delete(
            reverse("sshkey_handler", args=[keys[0].id])
        )
        self.assertEqual(http.client.FORBIDDEN, response.status_code, response)
        self.assertEqual(1, len(SSHKey.objects.filter(user=user)))

    def test_adding_works(self):
        key_string = get_data("data/test_rsa0.pub")
        response = self.client.post(
            reverse("sshkeys_handler"), data=dict(key=key_string)
        )
        self.assertEqual(http.client.CREATED, response.status_code)
        parsed_response = json_load_bytes(response.content)
        self.assertEqual(key_string, parsed_response["key"])
        added_key = get_one(SSHKey.objects.filter(user=self.user))
        self.assertEqual(key_string, added_key.key)

    def test_adding_works_with_user(self):
        self.become_admin()
        username = factory.make_name("user")
        user = factory.make_User(username=username)
        key_string = get_data("data/test_rsa0.pub")
        response = self.client.post(
            reverse("sshkeys_handler"),
            data=dict(key=key_string, user=username),
        )
        self.assertEqual(http.client.CREATED, response.status_code)
        parsed_response = json_load_bytes(response.content)
        self.assertEqual(key_string, parsed_response["key"])
        added_key = get_one(SSHKey.objects.filter(user=user))
        self.assertEqual(key_string, added_key.key)

    def test_adding_does_not_work_with_unknown_user(self):
        self.become_admin()
        username = factory.make_name("user")
        key_string = get_data("data/test_rsa0.pub")
        response = self.client.post(
            reverse("sshkeys_handler"),
            data=dict(key=key_string, user=username),
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response
        )
        self.assertIn(b"Supplied username", response.content)

    def test_adding_does_not_work_with_user_for_non_admin(self):
        username = factory.make_name("user")
        factory.make_User(username=username)
        key_string = get_data("data/test_rsa0.pub")
        response = self.client.post(
            reverse("sshkeys_handler"),
            data=dict(key=key_string, user=username),
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response
        )
        self.assertIn(b"Only administrators", response.content)

    def test_adding_catches_key_validation_errors(self):
        key_string = factory.make_string()
        response = self.client.post(
            reverse("sshkeys_handler"), data=dict(key=key_string)
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response
        )
        self.assertIn(b"Invalid", response.content)

    def test_adding_returns_badrequest_when_key_not_in_form(self):
        response = self.client.post(reverse("sshkeys_handler"))
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response
        )
        self.assertEqual(
            dict(key=["This field is required."]),
            json_load_bytes(response.content),
        )

    def test_import_ssh_keys_creates_keys_keysource_and_audit_event(self):
        protocol = random.choice(
            [KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]
        )
        auth_id = factory.make_name("auth_id")
        ks = f"{protocol}:{auth_id}"
        key_string = get_data("data/test_rsa0.pub")
        mock_get_protocol_keys = self.patch(
            keysource_module, "get_protocol_keys"
        )
        mock_get_protocol_keys.return_value = [key_string]
        response = self.client.post(
            reverse("sshkeys_handler"), data=dict(op="import", keysource=ks)
        )
        added_key = get_one(SSHKey.objects.filter(user=self.user))
        self.assertEqual(key_string, added_key.key)
        self.assertEqual(ks, str(added_key.keysource))
        self.assertEqual(http.client.OK, response.status_code, response)
        mock_get_protocol_keys.assert_called_once_with(protocol, auth_id)
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(event.description, "Imported SSH keys.")

    def test_import_ssh_keys_creates_keys_not_duplicate_keysource(self):
        protocol = random.choice(
            [KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]
        )
        auth_id = factory.make_name("auth_id")
        ks = f"{protocol}:{auth_id}"
        keysource = factory.make_KeySource(protocol=protocol, auth_id=auth_id)
        key_string = get_data("data/test_rsa0.pub")
        mock_get_protocol_keys = self.patch(
            keysource_module, "get_protocol_keys"
        )
        mock_get_protocol_keys.return_value = [key_string]
        response = self.client.post(
            reverse("sshkeys_handler"), data=dict(op="import", keysource=ks)
        )
        added_key = get_one(SSHKey.objects.filter(user=self.user))
        self.assertEqual(key_string, added_key.key)
        self.assertEqual(str(keysource), str(added_key.keysource))
        self.assertEqual(1, KeySource.objects.count())
        self.assertEqual(http.client.OK, response.status_code, response)
        mock_get_protocol_keys.assert_called_once_with(protocol, auth_id)

    def test_import_ssh_keys_crashes_for_ImportSSHKeysERROR(self):
        protocol = random.choice(
            [KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]
        )
        auth_id = factory.make_name("auth_id")
        ks = f"{protocol}:{auth_id}"
        mock_get_protocol_keys = self.patch(
            keysource_module, "get_protocol_keys"
        )
        mock_get_protocol_keys.side_effect = ImportSSHKeysError("error")
        response = self.client.post(
            reverse("sshkeys_handler"), data=dict(op="import", keysource=ks)
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_import_ssh_keys_crashes_for_RequestException(self):
        protocol = random.choice(
            [KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]
        )
        auth_id = factory.make_name("auth_id")
        ks = f"{protocol}:{auth_id}"
        mock_get_protocol_keys = self.patch(
            keysource_module, "get_protocol_keys"
        )
        mock_get_protocol_keys.side_effect = RequestException("error")
        response = self.client.post(
            reverse("sshkeys_handler"), data=dict(op="import", keysource=ks)
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )


class TestMAASAPIAnon(APITestCase.ForAnonymous):
    """The MAAS' handler is not accessible to anon users."""

    def test_anon_get_config_unauthorized(self):
        response = self.client.get(
            reverse("maas_handler"), {"op": "get_config"}
        )

        self.assertEqual(http.client.UNAUTHORIZED, response.status_code)

    def test_anon_set_config_unauthorized(self):
        response = self.client.post(
            reverse("maas_handler"), {"op": "set_config"}
        )

        self.assertEqual(http.client.UNAUTHORIZED, response.status_code)


class TestMAASAPIVersioning(APITestCase.ForAnonymousAndUserAndAdmin):
    clientfactories = {
        "user+pass": MAASSensibleClient,
        "oauth": MAASSensibleOAuthClient,
    }

    def test_api_version_handler_path(self):
        self.assertEqual("/MAAS/api/version/", reverse("api_version"))

    def test_v1_error_handler_path(self):
        self.assertEqual("/MAAS/api/1.0/", reverse("api_v1_error"))

    def test_get_api_version(self):
        response = self.client.get(reverse("api_version"))
        self.assertEqual(http.client.OK, response.status_code)
        self.assertIn("text/plain", response["Content-Type"])
        self.assertEqual(b"2.0", response.content)

    def test_old_api_request(self):
        old_api_url = reverse("api_v1_error") + "maas/" + factory.make_string()
        response = self.client.get(old_api_url)
        self.assertEqual(http.client.GONE, response.status_code)
        self.assertIn("text/plain", response["Content-Type"])
        self.assertEqual(
            b"The 1.0 API is no longer available. Please use API version 2.0.",
            response.content,
        )


class TestMAASAPI(APITestCase.ForUser):
    clientfactories = {
        "user+pass": MAASSensibleClient,
        "oauth": MAASSensibleOAuthClient,
    }

    def test_handler_path(self):
        self.assertEqual("/MAAS/api/2.0/maas/", reverse("maas_handler"))

    def test_simple_user_set_config_forbidden(self):
        response = self.client.post(
            reverse("maas_handler"), {"op": "set_config"}
        )

        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_get_config_requires_name_param(self):
        response = self.client.get(
            reverse("maas_handler"), {"op": "get_config"}
        )

        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual(b"No provided name!", response.content)

    def test_get_config_returns_config(self):
        name = "maas_name"
        value = factory.make_string()
        Config.objects.set_config(name, value)
        response = self.client.get(
            reverse("maas_handler"), {"op": "get_config", "name": name}
        )

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertIn("application/json", response["Content-Type"])
        self.assertEqual(value, parsed_result)

    def test_get_config_rejects_unknown_config_item(self):
        name = factory.make_string()
        value = factory.make_string()
        Config.objects.set_config(name, value)
        response = self.client.get(
            reverse("maas_handler"), {"op": "get_config", "name": name}
        )

        self.assertEqual(
            (
                http.client.BAD_REQUEST,
                {name: [INVALID_SETTING_MSG_TEMPLATE % name]},
            ),
            (response.status_code, json_load_bytes(response.content)),
        )

    def test_set_config_requires_name_param(self):
        self.become_admin()
        response = self.client.post(
            reverse("maas_handler"),
            {"op": "set_config", "value": factory.make_string()},
        )

        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual(b"No provided name!", response.content)

    def test_set_config_requires_string_name_param(self):
        self.become_admin()
        value = factory.make_string()
        response = self.client.post(
            reverse("maas_handler"),
            {
                "op": "set_config",
                "name": "",  # Invalid empty name.
                "value": value,
            },
        )

        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual(
            b"Invalid name: Please enter a value", response.content
        )

    def test_set_config_requires_value_param(self):
        self.become_admin()
        response = self.client.post(
            reverse("maas_handler"),
            {"op": "set_config", "name": factory.make_string()},
        )

        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual(b"No provided value!", response.content)

    def test_admin_set_config(self):
        self.become_admin()
        name = "maas_name"
        value = factory.make_string()
        response = self.client.post(
            reverse("maas_handler"),
            {"op": "set_config", "name": name, "value": value},
        )

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        stored_value = Config.objects.get_config(name)
        self.assertEqual(stored_value, value)

    def test_admin_set_config_rejects_unknown_config_item(self):
        self.become_admin()
        name = factory.make_string()
        value = factory.make_string()
        response = self.client.post(
            reverse("maas_handler"),
            {"op": "set_config", "name": name, "value": value},
        )

        self.assertEqual(
            (
                http.client.BAD_REQUEST,
                {name: [INVALID_SETTING_MSG_TEMPLATE % name]},
            ),
            (response.status_code, json_load_bytes(response.content)),
        )


class TestAPIErrors(APITransactionTestCase.ForUserAndAdmin):
    def test_internal_error_generates_proper_api_response(self):
        error_message = factory.make_string()

        # Monkey patch api.create_node to have it raise a RuntimeError.
        def raise_exception(*args, **kwargs):
            raise RuntimeError(error_message)

        self.patch(machines_module, "create_machine", raise_exception)
        response = self.client.post(reverse("machines_handler"), {})

        self.assertEqual(
            (
                http.client.INTERNAL_SERVER_ERROR,
                error_message.encode(settings.DEFAULT_CHARSET),
            ),
            (response.status_code, response.content),
        )
