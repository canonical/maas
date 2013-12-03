# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the commissioning-related portions of the MAAS API."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from base64 import b64encode
from datetime import (
    datetime,
    timedelta,
    )
import httplib
import json

from django.conf import settings
from django.core.urlresolvers import reverse
from maasserver.enum import NODE_STATUS
from maasserver.testing import reload_object
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    AdminLoggedInTestCase,
    LoggedInTestCase,
    )
from maastesting.utils import sample_binary_data
from metadataserver.models import CommissioningScript


class TestCommissioningTimeout(LoggedInTestCase):
    """Testing of commissioning timeout API."""

    def test_check_with_no_action(self):
        node = factory.make_node(status=NODE_STATUS.READY)
        response = self.client.post(
            reverse('nodes_handler'), {'op': 'check_commissioning'})
        # Anything that's not commissioning should be ignored.
        node = reload_object(node)
        self.assertEqual(
            (httplib.OK, NODE_STATUS.READY),
            (response.status_code, node.status))

    def test_check_with_commissioning_but_not_expired_node(self):
        node = factory.make_node(
            status=NODE_STATUS.COMMISSIONING)
        response = self.client.post(
            reverse('nodes_handler'), {'op': 'check_commissioning'})
        node = reload_object(node)
        self.assertEqual(
            (httplib.OK, NODE_STATUS.COMMISSIONING),
            (response.status_code, node.status))

    def test_check_with_commissioning_and_expired_node(self):
        # Have an interval 1 second longer than the timeout.
        interval = timedelta(seconds=1, minutes=settings.COMMISSIONING_TIMEOUT)
        updated_at = datetime.now() - interval
        node = factory.make_node(
            status=NODE_STATUS.COMMISSIONING, created=datetime.now(),
            updated=updated_at)

        response = self.client.post(
            reverse('nodes_handler'), {'op': 'check_commissioning'})
        self.assertEqual(
            (
                httplib.OK,
                NODE_STATUS.FAILED_TESTS,
                [node.system_id]
            ),
            (
                response.status_code,
                reload_object(node).status,
                [response_node['system_id']
                 for response_node in json.loads(response.content)],
            ))


class AdminCommissioningScriptsAPITest(AdminLoggedInTestCase):
    """Tests for `CommissioningScriptsHandler`."""

    def get_url(self):
        return reverse('commissioning_scripts_handler')

    def test_GET_lists_commissioning_scripts(self):
        # Use lower-case names.  The database and the test may use
        # different collation orders with different ideas about case
        # sensitivity.
        names = {factory.make_name('script').lower() for counter in range(5)}
        for name in names:
            factory.make_commissioning_script(name=name)

        response = self.client.get(self.get_url())

        self.assertEqual(
            (httplib.OK, sorted(names)),
            (response.status_code, json.loads(response.content)))

    def test_POST_creates_commissioning_script(self):
        # This uses Piston's built-in POST code, so there are no tests for
        # corner cases (like "script already exists") here.
        name = factory.make_name('script')
        content = factory.getRandomBytes()

        # Every uploaded file also has a name.  But this is completely
        # unrelated to the name we give to the commissioning script.
        response = self.client.post(
            self.get_url(),
            {
                'name': name,
                'content': factory.make_file_upload(content=content),
            })
        self.assertEqual(httplib.OK, response.status_code)

        returned_script = json.loads(response.content)
        self.assertEqual(
            (name, b64encode(content).decode("ascii")),
            (returned_script['name'], returned_script['content']))

        stored_script = CommissioningScript.objects.get(name=name)
        self.assertEqual(content, stored_script.content)


class CommissioningScriptsAPITest(APITestCase):

    def get_url(self):
        return reverse('commissioning_scripts_handler')

    def test_GET_is_forbidden(self):
        response = self.client.get(self.get_url())
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_POST_is_forbidden(self):
        response = self.client.post(
            self.get_url(),
            {'name': factory.make_name('script')})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)


class AdminCommissioningScriptAPITest(AdminLoggedInTestCase):
    """Tests for `CommissioningScriptHandler`."""

    def get_url(self, script_name):
        return reverse('commissioning_script_handler', args=[script_name])

    def test_GET_returns_script_contents(self):
        script = factory.make_commissioning_script()
        response = self.client.get(self.get_url(script.name))
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(script.content, response.content)

    def test_GET_preserves_binary_data(self):
        script = factory.make_commissioning_script(content=sample_binary_data)
        response = self.client.get(self.get_url(script.name))
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(sample_binary_data, response.content)

    def test_PUT_updates_contents(self):
        old_content = b'old:%s' % factory.getRandomString().encode('ascii')
        script = factory.make_commissioning_script(content=old_content)
        new_content = b'new:%s' % factory.getRandomString().encode('ascii')

        response = self.client_put(
            self.get_url(script.name),
            {'content': factory.make_file_upload(content=new_content)})
        self.assertEqual(httplib.OK, response.status_code)

        self.assertEqual(new_content, reload_object(script).content)

    def test_DELETE_deletes_script(self):
        script = factory.make_commissioning_script()
        self.client.delete(self.get_url(script.name))
        self.assertItemsEqual(
            [],
            CommissioningScript.objects.filter(name=script.name))


class CommissioningScriptAPITest(APITestCase):

    def get_url(self, script_name):
        return reverse('commissioning_script_handler', args=[script_name])

    def test_GET_is_forbidden(self):
        # It's not inconceivable that commissioning scripts contain
        # credentials of some sort.  There is no need for regular users
        # (consumers of the MAAS) to see these.
        script = factory.make_commissioning_script()
        response = self.client.get(self.get_url(script.name))
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_PUT_is_forbidden(self):
        script = factory.make_commissioning_script()
        response = self.client_put(
            self.get_url(script.name), {'content': factory.getRandomString()})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_DELETE_is_forbidden(self):
        script = factory.make_commissioning_script()
        response = self.client_put(self.get_url(script.name))
        self.assertEqual(httplib.FORBIDDEN, response.status_code)


class NodeCommissionResultHandlerAPITest(APITestCase):

    def test_list_returns_commissioning_results(self):
        commissioning_results = [
            factory.make_node_commission_result()
            for counter in range(3)]
        url = reverse('commissioning_results_handler')
        response = self.client.get(url, {'op': 'list'})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_results = json.loads(response.content)
        self.assertItemsEqual(
            [
                (
                    commissioning_result.name,
                    commissioning_result.script_result,
                    b64encode(commissioning_result.data),
                    commissioning_result.node.system_id,
                )
                for commissioning_result in commissioning_results
            ],
            [
                (
                    result.get('name'),
                    result.get('script_result'),
                    result.get('data'),
                    result.get('node').get('system_id'),
                )
                for result in parsed_results
            ]
        )

    def test_list_can_be_filtered_by_node(self):
        commissioning_results = [
            factory.make_node_commission_result()
            for counter in range(3)]
        url = reverse('commissioning_results_handler')
        response = self.client.get(
            url,
            {
                'op': 'list',
                'system_id': [
                    commissioning_results[0].node.system_id,
                    commissioning_results[1].node.system_id,
                ],
            }
        )
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_results = json.loads(response.content)
        self.assertItemsEqual(
            [b64encode(commissioning_results[0].data),
             b64encode(commissioning_results[1].data)],
            [result.get('data') for result in parsed_results])

    def test_list_can_be_filtered_by_name(self):
        commissioning_results = [
            factory.make_node_commission_result()
            for counter in range(3)]
        url = reverse('commissioning_results_handler')
        response = self.client.get(
            url,
            {
                'op': 'list',
                'name': commissioning_results[0].name
            }
        )
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_results = json.loads(response.content)
        self.assertItemsEqual(
            [b64encode(commissioning_results[0].data)],
            [result.get('data') for result in parsed_results])

    def test_list_displays_only_visible_nodes(self):
        node = factory.make_node(owner=factory.make_user())
        factory.make_node_commission_result(node)
        url = reverse('commissioning_results_handler')
        response = self.client.get(url, {'op': 'list'})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_results = json.loads(response.content)
        self.assertEqual([], parsed_results)
