# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import random
from unittest.mock import call

from django.core.exceptions import ValidationError
from django.http.response import Http404

from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    ConfigureDHCPParam,
)
from maasserver.models import DHCPSnippet, VersionedTextFile
from maasserver.models import dhcpsnippet as snippet_module
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import post_commit_hooks


class TestDHCPSnippet(MAASServerTestCase):
    def test_factory_make_DHCPSnippet(self):
        name = factory.make_name("dhcp_snippet")
        value = VersionedTextFile.objects.create(data=factory.make_string())
        description = factory.make_string()
        enabled = factory.pick_bool()
        dhcp_snippet = factory.make_DHCPSnippet(
            name, value, description, enabled
        )
        self.assertEqual(name, dhcp_snippet.name)
        self.assertEqual(value.data, dhcp_snippet.value.data)
        self.assertEqual(description, dhcp_snippet.description)
        self.assertEqual(enabled, dhcp_snippet.enabled)

    def test_factory_make_DHCPSnippet_sets_node(self):
        name = factory.make_name("dhcp_snippet")
        value = VersionedTextFile.objects.create(data=factory.make_string())
        description = factory.make_string()
        enabled = factory.pick_bool()
        node = factory.make_Node()
        dhcp_snippet = factory.make_DHCPSnippet(
            name, value, description, enabled, node
        )
        self.assertEqual(name, dhcp_snippet.name)
        self.assertEqual(value.data, dhcp_snippet.value.data)
        self.assertEqual(description, dhcp_snippet.description)
        self.assertEqual(enabled, dhcp_snippet.enabled)
        self.assertEqual(node, dhcp_snippet.node)

    def test_factory_make_DHCPSnippet_sets_subnet(self):
        name = factory.make_name("dhcp_snippet")
        value = VersionedTextFile.objects.create(data=factory.make_string())
        description = factory.make_string()
        enabled = factory.pick_bool()
        subnet = factory.make_Subnet()
        dhcp_snippet = factory.make_DHCPSnippet(
            name, value, description, enabled, subnet=subnet
        )
        self.assertEqual(name, dhcp_snippet.name)
        self.assertEqual(value.data, dhcp_snippet.value.data)
        self.assertEqual(description, dhcp_snippet.description)
        self.assertEqual(enabled, dhcp_snippet.enabled)
        self.assertEqual(subnet, dhcp_snippet.subnet)

    def test_factory_make_DHCPSnippet_sets_iprange(self):
        name = factory.make_name("dhcp_snippet")
        value = VersionedTextFile.objects.create(data=factory.make_string())
        description = factory.make_string()
        enabled = factory.pick_bool()
        subnet = factory.make_ipv4_Subnet_with_IPRanges()
        iprange = subnet.get_dynamic_ranges().first()

        with post_commit_hooks:
            iprange.save()

        dhcp_snippet = factory.make_DHCPSnippet(
            name, value, description, enabled, subnet=subnet, iprange=iprange
        )
        self.assertEqual(name, dhcp_snippet.name)
        self.assertEqual(value.data, dhcp_snippet.value.data)
        self.assertEqual(description, dhcp_snippet.description)
        self.assertEqual(enabled, dhcp_snippet.enabled)
        self.assertEqual(subnet, dhcp_snippet.subnet)
        self.assertEqual(iprange, dhcp_snippet.iprange)

    def test_can_only_set_snippet_for_node_or_subnet(self):
        node = factory.make_Node()
        subnet = factory.make_Subnet()
        self.assertRaises(
            ValidationError, factory.make_DHCPSnippet, node=node, subnet=subnet
        )

    def test_get_dhcp_snippet_or_404(self):
        dhcp_snippets = [factory.make_DHCPSnippet() for _ in range(3)]
        dhcp_snippet = random.choice(dhcp_snippets)
        self.assertEqual(
            dhcp_snippet,
            DHCPSnippet.objects.get_dhcp_snippet_or_404(dhcp_snippet.id),
        )

    def test_get_dhcp_snippet_or_404_raises_404(self):
        self.assertRaises(
            Http404,
            DHCPSnippet.objects.get_dhcp_snippet_or_404,
            random.randint(0, 100),
        )

    def test_filter_by_id(self):
        dhcp_snippet = factory.make_DHCPSnippet()
        self.assertEqual(
            dhcp_snippet, DHCPSnippet.objects.get(id=dhcp_snippet.id)
        )

    def test_filter_by_name(self):
        dhcp_snippet = factory.make_DHCPSnippet()
        self.assertEqual(
            dhcp_snippet, DHCPSnippet.objects.get(name=dhcp_snippet.name)
        )

    def test_delete_cleans_values(self):
        dhcp_snippet = factory.make_DHCPSnippet()
        value_ids = [dhcp_snippet.value.id]
        for _ in range(3):
            dhcp_snippet.value = dhcp_snippet.value.update(
                factory.make_string()
            )
            value_ids.append(dhcp_snippet.value.id)
        dhcp_snippet.delete()
        for i in value_ids:
            self.assertRaises(
                VersionedTextFile.DoesNotExist,
                VersionedTextFile.objects.get,
                id=i,
            )

    def test_delete_cleans_values_on_queryset(self):
        dhcp_snippet = factory.make_DHCPSnippet()
        value_ids = [dhcp_snippet.value.id]
        for _ in range(3):
            dhcp_snippet.value = dhcp_snippet.value.update(
                factory.make_string()
            )
            value_ids.append(dhcp_snippet.value.id)
        DHCPSnippet.objects.filter(id=dhcp_snippet.id).delete()
        for i in value_ids:
            self.assertRaises(
                VersionedTextFile.DoesNotExist,
                VersionedTextFile.objects.get,
                id=i,
            )

    def test_is_global(self):
        snippet = factory.make_DHCPSnippet(subnet=None, node=None)
        self.assertTrue(snippet.is_global)

    def test_is_global_node(self):
        node = factory.make_Machine()
        snippet = factory.make_DHCPSnippet(subnet=None, node=node)
        self.assertFalse(snippet.is_global)

    def test_is_global_subnet(self):
        subnet = factory.make_Subnet()
        snippet = factory.make_DHCPSnippet(subnet=subnet, node=None)
        self.assertFalse(snippet.is_global)

    def test_save_calls_configure_dhcp_workflow(self):
        mock_start_workflow = self.patch(snippet_module, "start_workflow")
        subnet = factory.make_Subnet()
        factory.make_DHCPSnippet(subnet=subnet, node=None)
        mock_start_workflow.assert_called_once_with(
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=ConfigureDHCPParam(
                subnet_ids=[subnet.id],
            ),
            task_queue="region",
        )

    def test_delete_calls_configure_dhcp_workflow(self):
        mock_start_workflow = self.patch(snippet_module, "start_workflow")
        subnet = factory.make_Subnet()
        snippet = factory.make_DHCPSnippet(subnet=subnet, node=None)

        with post_commit_hooks:
            snippet.delete()
        self.assertIn(
            call(
                workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
                param=ConfigureDHCPParam(subnet_ids=[subnet.id]),
                task_queue="region",
            ),
            mock_start_workflow.mock_calls,
        )
