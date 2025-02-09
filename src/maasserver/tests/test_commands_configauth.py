# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the configauth command."""

from contextlib import contextmanager
from datetime import timedelta
import json
import tempfile
import unittest

from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from maasserver.management.commands import configauth
from maasserver.models.rbacsync import RBAC_ACTION, RBACLastSync, RBACSync
from maasserver.rbac import FakeRBACUserClient
from maasserver.secrets import SecretManager
from maasserver.testing.testcase import MAASServerTestCase


class TestConfigAuthCommand(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.read_input = self.patch(configauth, "read_input")
        self.read_input.return_value = ""
        self.mock_print = self.patch(configauth, "print")
        self.rbac_user_client = FakeRBACUserClient()
        mock_client = self.patch(configauth, "RBACUserClient")
        mock_client.return_value = self.rbac_user_client

    @contextmanager
    def agent_file(self):
        with tempfile.NamedTemporaryFile(mode="w+") as agent_file:
            config = {
                "key": {"public": "public-key", "private": "private-key"},
                "agents": [
                    {
                        "url": "http://example.com:1234",
                        "username": "user@admin",
                    }
                ],
            }
            json.dump(config, agent_file)
            agent_file.flush()
            yield agent_file.name

    def printout(self):
        prints = []
        for call in self.mock_print.mock_calls:
            _, output, _ = call
            # Empty tuple if print is called with no text
            output = output[0] if output else ""
            prints.append(output)
        return "\n".join(prints)

    def test_configauth_changes_empty_string(self):
        manager = SecretManager()
        manager.set_composite_secret(
            "external-auth", {"url": "http://example.com/candid"}
        )
        call_command("configauth", candid_agent_file="")
        self.assertEqual(
            manager.get_composite_secret("external-auth")["url"], ""
        )

    def test_configauth_changes_auth_prompt_default(self):
        self.read_input.return_value = ""
        call_command("configauth")
        self.assertEqual(
            SecretManager().get_composite_secret("external-auth"),
            {
                "url": "",
                "domain": "",
                "user": "",
                "key": "",
                "admin-group": "",
                "rbac-url": "",
            },
        )

    def test_configauth_changes_auth_invalid_rbac_url(self):
        self.assertRaises(
            configauth.InvalidURLError,
            call_command,
            "configauth",
            rbac_url="example.com",
        )

    def test_configauth_delete_sessions(self):
        session = Session(
            session_key="session_key",
            expire_date=timezone.now() + timedelta(days=1),
        )
        session.save()
        call_command("configauth", rbac_url="")
        self.assertFalse(Session.objects.all().exists())

    def test_update_auth_details(self):
        auth_details = configauth._AuthDetails()
        with self.agent_file() as agent_file_name:
            configauth.update_auth_details_from_agent_file(
                agent_file_name, auth_details
            )
        self.assertEqual(auth_details.url, "http://example.com:1234")
        self.assertEqual(auth_details.user, "user@admin")
        self.assertEqual(auth_details.key, "private-key")

    def test_configauth_interactive(self):
        with self.agent_file() as agent_file_name:
            self.read_input.side_effect = [
                "",
                agent_file_name,
                "mydomain",
                "admins",
            ]
            call_command("configauth")
        self.assertEqual(
            SecretManager().get_composite_secret("external-auth"),
            {
                "url": "http://example.com:1234",
                "domain": "mydomain",
                "user": "user@admin",
                "key": "private-key",
                "admin-group": "admins",
                "rbac-url": "",
            },
        )

    def test_configauth_interactive_domain(self):
        with self.agent_file() as agent_file_name:
            self.read_input.return_value = "mydomain"
            call_command(
                "configauth", rbac_url="", candid_agent_file=agent_file_name
            )
        self.assertEqual(
            SecretManager().get_composite_secret("external-auth")["domain"],
            "mydomain",
        )

    def test_configauth_interactive_domain_empty(self):
        with self.agent_file() as agent_file_name:
            self.read_input.return_value = ""
            call_command(
                "configauth", rbac_url="", candid_agent_file=agent_file_name
            )
        self.assertEqual(
            SecretManager().get_composite_secret("external-auth")["domain"],
            "",
        )

    def test_configauth_interactive_key(self):
        with self.agent_file() as agent_file_name:
            self.read_input.return_value = "private-key"
            call_command(
                "configauth",
                rbac_url="",
                candid_agent_file=agent_file_name,
                candid_domain="mydomain",
            )
        self.assertEqual(
            SecretManager().get_composite_secret("external-auth")["key"],
            "private-key",
        )

    def test_configauth_not_interactive(self):
        with self.agent_file() as agent_file_name:
            call_command(
                "configauth",
                rbac_url="",
                candid_agent_file=agent_file_name,
                candid_domain="mydomain",
                candid_admin_group="admins",
            )
        self.assertEqual(
            SecretManager().get_composite_secret("external-auth"),
            {
                "url": "http://example.com:1234",
                "domain": "mydomain",
                "user": "user@admin",
                "key": "private-key",
                "admin-group": "admins",
                "rbac-url": "",
            },
        )
        self.read_input.assert_not_called()

    def test_configauth_agentfile_not_found(self):
        error = self.assertRaises(
            CommandError,
            call_command,
            "configauth",
            rbac_url="",
            candid_agent_file="/not/here",
        )
        self.assertEqual(
            str(error), "[Errno 2] No such file or directory: '/not/here'"
        )

    def test_configauth_domain_none(self):
        with self.agent_file() as agent_file_name:
            call_command(
                "configauth",
                rbac_url="",
                candid_agent_file=agent_file_name,
                candid_domain="none",
            )
        self.assertEqual(
            SecretManager().get_composite_secret("external-auth")["domain"], ""
        )

    def test_configauth_json_empty(self):
        call_command("configauth", json=True)
        self.read_input.assert_not_called()
        [print_call] = self.mock_print.mock_calls
        _, [output], kwargs = print_call
        self.assertEqual({}, kwargs)
        self.assertEqual(
            {
                "external_auth_url": "",
                "external_auth_domain": "",
                "external_auth_user": "",
                "external_auth_key": "",
                "external_auth_admin_group": "",
                "rbac_url": "",
            },
            json.loads(output),
        )

    def test_configauth_json_full(self):
        secret_manager = SecretManager()
        secret_manager.set_composite_secret(
            "external-auth",
            {
                "url": "http://candid.example.com/",
                "domain": "mydomain",
                "user": "maas",
                "key": "secret maas key",
                "admin-group": "admins",
                "rbac-url": "http://rbac.example.com/",
            },
        )
        mock_print = self.patch(configauth, "print")
        call_command("configauth", json=True)
        self.read_input.assert_not_called()
        [print_call] = mock_print.mock_calls
        _, [output], kwargs = print_call
        self.assertEqual({}, kwargs)
        self.assertEqual(
            {
                "external_auth_url": "http://candid.example.com/",
                "external_auth_domain": "mydomain",
                "external_auth_user": "maas",
                "external_auth_key": "secret maas key",
                "external_auth_admin_group": "admins",
                "rbac_url": "http://rbac.example.com/",
            },
            json.loads(output),
        )

    def test_configauth_rbac_with_name_existing(self):
        self.rbac_user_client.services = [
            {
                "name": "mymaas",
                "$uri": "/api/rbac/v1/service/4",
                "pending": True,
                "product": {"$ref/api/rbac/v1/product/2"},
            }
        ]
        call_command(
            "configauth",
            rbac_url="http://rbac.example.com",
            rbac_service_name="mymaas",
        )
        self.read_input.assert_not_called()
        self.assertEqual(
            SecretManager().get_composite_secret("external-auth")["rbac-url"],
            "http://rbac.example.com",
        )
        self.assertEqual(
            self.rbac_user_client.registered_services,
            ["/api/rbac/v1/service/4"],
        )

    def test_configauth_rbac_with_name_create(self):
        patch_prompt = self.patch(configauth, "prompt_for_choices")
        patch_prompt.return_value = "yes"
        call_command(
            "configauth",
            rbac_url="http://rbac.example.com",
            rbac_service_name="maas",
        )
        patch_prompt.assert_called_once()
        self.assertEqual(
            SecretManager().get_composite_secret("external-auth")["rbac-url"],
            "http://rbac.example.com",
        )
        self.assertEqual(
            self.rbac_user_client.registered_services,
            ["/api/rbac/v1/service/4"],
        )

    def test_configauth_rbac_with_name_abort(self):
        patch_prompt = self.patch(configauth, "prompt_for_choices")
        patch_prompt.return_value = "no"
        error = self.assertRaises(
            CommandError,
            call_command,
            "configauth",
            rbac_url="http://rbac.example.com",
            rbac_service_name="maas",
        )
        self.assertEqual(str(error), "Registration with RBAC service canceled")
        patch_prompt.assert_called_once()
        self.assertIsNone(
            SecretManager().get_composite_secret(
                "external-auth", default=None
            ),
        )
        self.assertEqual(self.rbac_user_client.registered_services, [])

    def test_configauth_rbac_registration_list(self):
        self.rbac_user_client.services = [
            {
                "name": "mymaas",
                "$uri": "/api/rbac/v1/service/4",
                "pending": False,
                "product": {"$ref/api/rbac/v1/product/2"},
            },
            {
                "name": "mymaas2",
                "$uri": "/api/rbac/v1/service/12",
                "pending": True,
                "product": {"$ref/api/rbac/v1/product/2"},
            },
        ]
        # The index of the service to register is prompted
        self.read_input.side_effect = ["2"]
        call_command("configauth", rbac_url="http://rbac.example.com")
        secret = SecretManager().get_composite_secret("external-auth")
        self.assertEqual(secret["rbac-url"], "http://rbac.example.com")
        self.assertEqual(secret["url"], "http://auth.example.com")
        self.assertEqual(secret["user"], "u-1")
        self.assertNotEqual(secret["key"], "")
        self.assertEqual(secret["domain"], "")
        self.assertEqual(secret["admin-group"], "")
        prints = self.printout()
        self.assertIn("1 - mymaas", prints)
        self.assertIn("2 - mymaas2 (pending)", prints)
        self.assertIn('Service "mymaas2" registered', prints)

    def test_configauth_rbac_registration_invalid_index(self):
        self.rbac_user_client.services = [
            {
                "name": "mymaas",
                "$uri": "/api/rbac/v1/service/4",
                "pending": True,
                "product": {"$ref/api/rbac/v1/product/2"},
            }
        ]
        self.read_input.side_effect = ["2"]
        error = self.assertRaises(
            CommandError,
            call_command,
            "configauth",
            rbac_url="http://rbac.example.com",
        )
        self.assertEqual(str(error), "Invalid index")

    def test_configauth_rbac_no_registerable(self):
        error = self.assertRaises(
            CommandError,
            call_command,
            "configauth",
            rbac_url="http://rbac.example.com",
        )
        self.assertEqual(
            str(error),
            "No registerable MAAS service on the specified RBAC server",
        )

    def test_configauth_rbac_url_none(self):
        with self.agent_file() as agent_file_name:
            call_command(
                "configauth",
                rbac_url="none",
                candid_agent_file=agent_file_name,
                candid_domain="domain",
                candid_admin_group="admins",
            )
        self.read_input.assert_not_called()
        self.assertEqual(
            SecretManager().get_composite_secret("external-auth")["rbac-url"],
            "",
        )

    def test_configauth_rbac_url_none_clears_lastsync_and_sync(self):
        RBACLastSync.objects.create(resource_type="resource-pool", sync_id=0)
        RBACSync.objects.create(resource_type="")
        call_command("configauth", rbac_url="none", candid_agent_file="none")
        self.assertEqual(
            SecretManager().get_composite_secret("external-auth")["rbac-url"],
            "",
        )
        self.assertFalse(RBACLastSync.objects.all().exists())
        self.assertFalse(RBACSync.objects.all().exists())

    def test_configauth_rbac_clears_lastsync_and_full_sync(self):
        RBACLastSync.objects.create(resource_type="resource-pool", sync_id=0)
        self.rbac_user_client.services = [
            {
                "name": "mymaas",
                "$uri": "/api/rbac/v1/service/4",
                "pending": True,
                "product": {"$ref/api/rbac/v1/product/2"},
            }
        ]
        call_command(
            "configauth",
            rbac_url="http://rbac.example.com",
            rbac_service_name="mymaas",
        )
        self.read_input.assert_not_called()
        self.assertEqual(
            SecretManager().get_composite_secret("external-auth")["rbac-url"],
            "http://rbac.example.com",
        )
        self.assertFalse(RBACLastSync.objects.all().exists())
        latest = RBACSync.objects.order_by("-id").first()
        self.assertEqual(RBAC_ACTION.FULL, latest.action)
        self.assertEqual("", latest.resource_type)
        self.assertEqual("configauth command called", latest.source)


class TestIsValidUrl(unittest.TestCase):
    def test_valid_schemes(self):
        for scheme in ["http", "https"]:
            url = f"{scheme}://example.com/candid"
            self.assertTrue(configauth.is_valid_url(url))

    def test_invalid_schemes(self):
        for scheme in ["ftp", "git+ssh"]:
            url = f"{scheme}://example.com/candid"
            self.assertFalse(configauth.is_valid_url(url))
