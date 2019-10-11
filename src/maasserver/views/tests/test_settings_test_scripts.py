# Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver test scripts views."""

__all__ = []

import http.client

from django.conf import settings
from lxml.html import fromstring
from maasserver.models import Event
from maasserver.testing import extract_redirect, get_content_links
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.django_urls import reverse
from maasserver.views.settings_test_scripts import TEST_SCRIPTS_ANCHOR
from metadataserver.enum import SCRIPT_TYPE
from metadataserver.models import Script
from provisioningserver.events import AUDIT
from testtools.matchers import ContainsAll


class TestScriptListingTest(MAASServerTestCase):
    def test_settings_contains_names_and_content_of_scripts(self):
        self.client.login(user=factory.make_admin())
        scripts = [
            factory.make_Script(script_type=SCRIPT_TYPE.TESTING),
            factory.make_Script(script_type=SCRIPT_TYPE.TESTING),
            factory.make_Script(script_type=SCRIPT_TYPE.TESTING, default=True),
        ]
        response = self.client.get(reverse("settings_scripts"))
        names = [script.name for script in scripts[:-1]]
        contents = [script.script.data for script in scripts[:-1]]
        self.assertThat(
            response.content,
            ContainsAll(
                [name.encode(settings.DEFAULT_CHARSET) for name in names]
            ),
        )
        self.assertThat(
            response.content,
            ContainsAll([content.encode() for content in contents]),
        )

    def test_settings_link_to_upload_script(self):
        self.client.login(user=factory.make_admin())
        links = get_content_links(self.client.get(reverse("settings_scripts")))
        script_add_link = reverse("test-script-add")
        self.assertIn(script_add_link, links)

    def test_settings_contains_links_to_delete_scripts(self):
        self.client.login(user=factory.make_admin())
        scripts = {
            factory.make_Script(script_type=SCRIPT_TYPE.TESTING),
            factory.make_Script(script_type=SCRIPT_TYPE.TESTING),
        }
        links = get_content_links(self.client.get(reverse("settings_scripts")))
        script_delete_links = [
            reverse("test-script-delete", args=[script.id])
            for script in scripts
        ]
        self.assertThat(links, ContainsAll(script_delete_links))

    def test_settings_contains_test_scripts_slot_anchor(self):
        self.client.login(user=factory.make_admin())
        response = self.client.get(reverse("settings_scripts"))
        document = fromstring(response.content)
        slots = document.xpath("//div[@id='%s']" % TEST_SCRIPTS_ANCHOR)
        self.assertEqual(
            1, len(slots), "Missing anchor '%s'" % TEST_SCRIPTS_ANCHOR
        )


class TestScriptDeleteTest(MAASServerTestCase):
    def test_can_delete_test_script(self):
        self.client.login(user=factory.make_admin())
        script = factory.make_Script()
        delete_link = reverse("test-script-delete", args=[script.id])
        response = self.client.post(delete_link, {"post": "yes"})
        self.assertEqual(
            (http.client.FOUND, reverse("settings_scripts")),
            (response.status_code, extract_redirect(response)),
        )
        self.assertFalse(Script.objects.filter(id=script.id).exists())

    def test_delete_script_creates_audit_event(self):
        self.client.login(user=factory.make_admin())
        script = factory.make_Script()
        script_name = script.name
        delete_link = reverse("test-script-delete", args=[script.id])
        self.client.post(delete_link, {"post": "yes"})
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(
            event.description, "Deleted script '%s'." % script_name
        )


class TestScriptUploadTest(MAASServerTestCase):
    def test_can_create_test_script(self):
        self.client.login(user=factory.make_admin())
        content = factory.make_script_content().encode("ascii")
        name = factory.make_name("filename")
        create_link = reverse("test-script-add")
        filepath = self.make_file(name=name, contents=content)
        with open(filepath) as fp:
            response = self.client.post(
                create_link, {"name": name, "content": fp}
            )
        self.assertEqual(
            (http.client.FOUND, reverse("settings_scripts")),
            (response.status_code, extract_redirect(response)),
        )
        new_script = Script.objects.get(name=name)
        self.assertEquals(name, new_script.name)
        self.assertEquals(content, new_script.script.data.encode())
