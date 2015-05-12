# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver clusters views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import httplib

from django.core.urlresolvers import reverse
from lxml.html import fromstring
from maasserver.testing import (
    extract_redirect,
    get_content_links,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.views.settings_commissioning_scripts import (
    COMMISSIONING_SCRIPTS_ANCHOR,
)
from metadataserver.models import CommissioningScript
from testtools.matchers import (
    ContainsAll,
    MatchesStructure,
)


class CommissioningScriptListingTest(MAASServerTestCase):

    def test_settings_contains_names_and_content_of_scripts(self):
        self.client_log_in(as_admin=True)
        scripts = {
            factory.make_CommissioningScript(),
            factory.make_CommissioningScript(),
            }
        response = self.client.get(reverse('settings'))
        names = [script.name for script in scripts]
        contents = [script.content for script in scripts]
        self.assertThat(response.content, ContainsAll(names + contents))

    def test_settings_link_to_upload_script(self):
        self.client_log_in(as_admin=True)
        links = get_content_links(self.client.get(reverse('settings')))
        script_add_link = reverse('commissioning-script-add')
        self.assertIn(script_add_link, links)

    def test_settings_contains_links_to_delete_scripts(self):
        self.client_log_in(as_admin=True)
        scripts = {
            factory.make_CommissioningScript(),
            factory.make_CommissioningScript(),
            }
        links = get_content_links(self.client.get(reverse('settings')))
        script_delete_links = [
            reverse('commissioning-script-delete', args=[script.id])
            for script in scripts]
        self.assertThat(links, ContainsAll(script_delete_links))

    def test_settings_contains_commissioning_scripts_slot_anchor(self):
        self.client_log_in(as_admin=True)
        response = self.client.get(reverse('settings'))
        document = fromstring(response.content)
        slots = document.xpath(
            "//div[@id='%s']" % COMMISSIONING_SCRIPTS_ANCHOR)
        self.assertEqual(
            1, len(slots),
            "Missing anchor '%s'" % COMMISSIONING_SCRIPTS_ANCHOR)


class CommissioningScriptDeleteTest(MAASServerTestCase):

    def test_can_delete_commissioning_script(self):
        self.client_log_in(as_admin=True)
        script = factory.make_CommissioningScript()
        delete_link = reverse('commissioning-script-delete', args=[script.id])
        response = self.client.post(delete_link, {'post': 'yes'})
        self.assertEqual(
            (httplib.FOUND, reverse('settings')),
            (response.status_code, extract_redirect(response)))
        self.assertFalse(
            CommissioningScript.objects.filter(id=script.id).exists())


class CommissioningScriptUploadTest(MAASServerTestCase):

    def test_can_create_commissioning_script(self):
        self.client_log_in(as_admin=True)
        content = factory.make_string()
        name = factory.make_name('filename')
        create_link = reverse('commissioning-script-add')
        filepath = self.make_file(name=name, contents=content)
        with open(filepath) as fp:
            response = self.client.post(
                create_link, {'name': name, 'content': fp})
        self.assertEqual(
            (httplib.FOUND, reverse('settings')),
            (response.status_code, extract_redirect(response)))
        new_script = CommissioningScript.objects.get(name=name)
        self.assertThat(
            new_script,
            MatchesStructure.byEquality(name=name, content=content))
