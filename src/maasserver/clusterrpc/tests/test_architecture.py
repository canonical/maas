# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `list_supported_architectures`."""


from collections import OrderedDict

from maasserver.clusterrpc import architecture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestListSupportedArchitectures(MAASServerTestCase):
    def test_lists_architecture_choices(self):
        arch = factory.make_name("arch")
        description = factory.make_name("description")
        self.patch(architecture, "call_clusters").return_value = iter(
            [{"architectures": [{"name": arch, "description": description}]}]
        )
        choices = architecture.list_supported_architectures()
        self.assertEqual(OrderedDict([(arch, description)]), choices)

    def test_merges_results_from_multiple_nodegroups(self):
        arch1, arch2, arch3 = (factory.make_name("arch") for _ in range(3))
        self.patch(architecture, "call_clusters").return_value = iter(
            [
                {
                    "architectures": [
                        {"name": arch1, "description": arch1},
                        {"name": arch3, "description": arch3},
                    ]
                },
                {
                    "architectures": [
                        {"name": arch2, "description": arch2},
                        {"name": arch3, "description": arch3},
                    ]
                },
            ]
        )
        choices = architecture.list_supported_architectures()
        expected_choices = OrderedDict(
            (name, name) for name in sorted([arch1, arch2, arch3])
        )
        self.assertEqual(expected_choices, choices)

    def test_returns_empty_list_if_there_are_no_node_groups(self):
        self.assertEqual(
            OrderedDict(), architecture.list_supported_architectures()
        )

    def test_sorts_results(self):
        architectures = [factory.make_name("arch") for _ in range(3)]
        self.patch(architecture, "call_clusters").return_value = iter(
            [
                {
                    "architectures": [
                        {
                            "name": arch,
                            "description": factory.make_name("desc"),
                        }
                        for arch in architectures
                    ]
                }
            ]
        )
        self.assertEqual(
            sorted(architectures),
            sorted(architecture.list_supported_architectures()),
        )
