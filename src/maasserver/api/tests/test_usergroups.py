#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `UserGroup` API."""

import http.client
import json

from django.conf import settings
from django.urls import reverse

from maasserver.auth.tests.test_auth import OpenFGAMockMixin
from maasserver.testing.api import APITestCase


def _parse(response):
    return json.loads(response.content.decode(settings.DEFAULT_CHARSET))


def _create_group(client, name, description=None):
    """Helper to create a group and return the parsed response dict."""
    data = {"name": name}
    if description is not None:
        data["description"] = description
    resp = client.post(reverse("usergroups_handler"), data)
    return _parse(resp), resp


class TestUserGroupsAPI(APITestCase.ForUser):
    """Tests for the UserGroups collection endpoint."""

    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/groups/", reverse("usergroups_handler")
        )

    def test_list_default_groups(self):
        self.become_admin()
        response = self.client.get(reverse("usergroups_handler"))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertCountEqual(
            [
                {
                    "description": "Default administrators group",
                    "id": 1,
                    "name": "Administrators",
                    "resource_uri": "/MAAS/api/2.0/groups/1/",
                },
                {
                    "description": "Default users group",
                    "id": 2,
                    "name": "Users",
                    "resource_uri": "/MAAS/api/2.0/groups/2/",
                },
            ],
            _parse(response),
        )

    def test_list_returns_groups(self):
        self.become_admin()
        _create_group(self.client, "group-a", "Group A")
        _create_group(self.client, "group-b", "Group B")
        response = self.client.get(reverse("usergroups_handler"))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed = _parse(response)
        names = {g["name"] for g in parsed}
        self.assertIn("group-a", names)
        self.assertIn("group-b", names)

    def test_list_includes_resource_uri(self):
        self.become_admin()
        created, _ = _create_group(self.client, "uri-group")
        response = self.client.get(reverse("usergroups_handler"))
        parsed = _parse(response)
        group = [g for g in parsed if g["name"] == "uri-group"][0]
        self.assertEqual(
            f"/MAAS/api/2.0/groups/{created['id']}/",
            group["resource_uri"],
        )

    def test_create_requires_admin(self):
        response = self.client.post(
            reverse("usergroups_handler"),
            {"name": "test-group"},
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_create(self):
        self.become_admin()
        created, response = _create_group(
            self.client, "new-group", "A new group"
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual("new-group", created["name"])
        self.assertEqual("A new group", created["description"])
        self.assertIn("id", created)
        self.assertIn("resource_uri", created)

    def test_create_without_description(self):
        self.become_admin()
        created, response = _create_group(self.client, "no-desc-group")
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual("no-desc-group", created["name"])
        self.assertEqual("", created["description"])

    def test_create_requires_name(self):
        self.become_admin()
        response = self.client.post(
            reverse("usergroups_handler"),
            {"description": "no name"},
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )


class TestUserGroupAPI(APITestCase.ForUser):
    """Tests for the UserGroup single-resource endpoint."""

    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/groups/1/",
            reverse("usergroup_handler", args=[1]),
        )

    def test_read(self):
        self.become_admin()
        created, _ = _create_group(self.client, "read-group", "Readable")
        group_id = created["id"]

        response = self.client.get(
            reverse("usergroup_handler", args=[group_id])
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed = _parse(response)
        self.assertEqual("read-group", parsed["name"])
        self.assertEqual("Readable", parsed["description"])
        self.assertEqual(
            f"/MAAS/api/2.0/groups/{group_id}/", parsed["resource_uri"]
        )

    def test_read_404(self):
        self.become_admin()
        response = self.client.get(reverse("usergroup_handler", args=[99999]))
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_update_requires_admin(self):
        self.become_admin()
        created, _ = _create_group(self.client, "update-group")
        group_id = created["id"]

        self.user.is_superuser = False
        self.user.save()

        response = self.client.put(
            reverse("usergroup_handler", args=[group_id]),
            {"name": "new-name"},
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_update(self):
        self.become_admin()
        created, _ = _create_group(self.client, "old-name", "old desc")
        group_id = created["id"]

        response = self.client.put(
            reverse("usergroup_handler", args=[group_id]),
            {"name": "new-name", "description": "new desc"},
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed = _parse(response)
        self.assertEqual("new-name", parsed["name"])
        self.assertEqual("new desc", parsed["description"])

    def test_update_name_only(self):
        self.become_admin()
        created, _ = _create_group(self.client, "partial-name", "keep this")
        group_id = created["id"]

        response = self.client.put(
            reverse("usergroup_handler", args=[group_id]),
            {"name": "changed-name"},
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed = _parse(response)
        self.assertEqual("changed-name", parsed["name"])
        self.assertEqual("keep this", parsed["description"])

    def test_update_description_only(self):
        self.become_admin()
        created, _ = _create_group(self.client, "keep-name", "old")
        group_id = created["id"]

        response = self.client.put(
            reverse("usergroup_handler", args=[group_id]),
            {"description": "updated"},
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed = _parse(response)
        self.assertEqual("keep-name", parsed["name"])
        self.assertEqual("updated", parsed["description"])

    def test_update_404(self):
        self.become_admin()
        response = self.client.put(
            reverse("usergroup_handler", args=[99999]),
            {"name": "nope"},
        )
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_delete_requires_admin(self):
        self.become_admin()
        created, _ = _create_group(self.client, "delete-group")
        group_id = created["id"]

        self.user.is_superuser = False
        self.user.save()

        response = self.client.delete(
            reverse("usergroup_handler", args=[group_id])
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_delete(self):
        self.become_admin()
        created, _ = _create_group(self.client, "to-delete")
        group_id = created["id"]

        response = self.client.delete(
            reverse("usergroup_handler", args=[group_id])
        )
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )

        # Verify it's gone
        response = self.client.get(
            reverse("usergroup_handler", args=[group_id])
        )
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_delete_404(self):
        self.become_admin()
        response = self.client.delete(
            reverse("usergroup_handler", args=[99999])
        )
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )


class TestUserGroupsOpenFGAIntegration(OpenFGAMockMixin, APITestCase.ForUser):
    def _create_group_as_admin(self, name, description="test"):
        """Create a group using edit permission, then return its id."""
        self.openfga_client.can_edit_identities.return_value = True
        created, resp = _create_group(self.client, name, description)
        self.assertEqual(http.client.OK, resp.status_code, resp.content)
        self.openfga_client.reset_mock()
        return created["id"]

    def test_list_requires_can_view_identities(self):
        self.openfga_client.can_view_identities.return_value = True
        response = self.client.get(reverse("usergroups_handler"))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.openfga_client.can_view_identities.assert_called_once_with(
            self.user
        )

    def test_list_denied_without_view_permission(self):
        self.openfga_client.can_view_identities.return_value = False
        response = self.client.get(reverse("usergroups_handler"))
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_create_requires_can_edit_identities(self):
        self.openfga_client.can_edit_identities.return_value = True
        _, response = _create_group(self.client, "openfga-group", "test")
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.openfga_client.can_edit_identities.assert_called_once_with(
            self.user
        )

    def test_create_denied_without_edit_permission(self):
        self.openfga_client.can_edit_identities.return_value = False
        response = self.client.post(
            reverse("usergroups_handler"),
            {"name": "denied-group"},
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_read_requires_can_view_identities(self):
        group_id = self._create_group_as_admin("view-group")
        self.openfga_client.can_view_identities.return_value = True
        response = self.client.get(
            reverse("usergroup_handler", args=[group_id])
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.openfga_client.can_view_identities.assert_called_once_with(
            self.user
        )

    def test_read_denied_without_view_permission(self):
        group_id = self._create_group_as_admin("no-view-group")
        self.openfga_client.can_view_identities.return_value = False
        response = self.client.get(
            reverse("usergroup_handler", args=[group_id])
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_update_requires_can_edit_identities(self):
        group_id = self._create_group_as_admin("edit-group")
        self.openfga_client.can_edit_identities.return_value = True
        response = self.client.put(
            reverse("usergroup_handler", args=[group_id]),
            {"name": "edited"},
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.openfga_client.can_edit_identities.assert_called_once_with(
            self.user
        )

    def test_update_denied_without_edit_permission(self):
        group_id = self._create_group_as_admin("no-edit-group")
        self.openfga_client.can_edit_identities.return_value = False
        response = self.client.put(
            reverse("usergroup_handler", args=[group_id]),
            {"name": "nope"},
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_delete_requires_can_edit_identities(self):
        group_id = self._create_group_as_admin("del-group")
        self.openfga_client.can_edit_identities.return_value = True
        response = self.client.delete(
            reverse("usergroup_handler", args=[group_id])
        )
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        self.openfga_client.can_edit_identities.assert_called_once_with(
            self.user
        )

    def test_delete_denied_without_edit_permission(self):
        group_id = self._create_group_as_admin("no-del-group")
        self.openfga_client.can_edit_identities.return_value = False
        response = self.client.delete(
            reverse("usergroup_handler", args=[group_id])
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )
