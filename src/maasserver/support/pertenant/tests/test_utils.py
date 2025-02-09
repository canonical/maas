# Copyright 2013-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the utilities of the per-tenant file storage work."""

from django.urls import reverse

from maasserver.support.pertenant.utils import (
    extract_bootstrap_node_system_id,
    get_bootstrap_node_owner,
    PROVIDER_STATE_FILENAME,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.utils import sample_binary_data


def make_provider_state_file(node=None):
    """Create a 'provider-state' file with a reference (zookeeper-instances)
    to a node.
    """
    if node is None:
        node = factory.make_Node()
    node_link = reverse("node_handler", args=[node.system_id])
    content = "zookeeper-instances: [%s]\n" % node_link
    content_data = content.encode("ascii")
    return factory.make_FileStorage(
        filename=PROVIDER_STATE_FILENAME, content=content_data, owner=None
    )


class TestExtractBootstrapNodeSystemId(MAASServerTestCase):
    def test_parses_valid_provider_state_file(self):
        node = factory.make_Node()
        provider_state_file = make_provider_state_file(node=node)
        system_id = extract_bootstrap_node_system_id(
            provider_state_file.content
        )
        self.assertEqual(system_id, node.system_id)

    def test_returns_None_if_parsing_fails(self):
        invalid_contents = [
            "%",  # invalid yaml
            sample_binary_data,  # binary content (invalid yaml)
            "invalid content",  # invalid provider-state content
            "zookeeper-instances: []",  # no instances listed
        ]
        for invalid_content in invalid_contents:
            self.assertIsNone(
                extract_bootstrap_node_system_id(invalid_content)
            )


class TestGetBootstrapNodeOwner(MAASServerTestCase):
    def test_returns_None_if_no_provider_state_file(self):
        self.assertIsNone(get_bootstrap_node_owner())

    def test_returns_owner_if_node_found(self):
        node = factory.make_Node(owner=factory.make_User())
        make_provider_state_file(node=node)
        self.assertEqual(node.owner, get_bootstrap_node_owner())

    def test_returns_None_if_node_does_not_exist(self):
        node = factory.make_Node(owner=factory.make_User())
        make_provider_state_file(node=node)
        node.delete()
        self.assertIsNone(get_bootstrap_node_owner())

    def test_returns_None_if_invalid_yaml(self):
        invalid_content = b"%"
        factory.make_FileStorage(
            filename=PROVIDER_STATE_FILENAME, content=invalid_content
        )
        self.assertIsNone(get_bootstrap_node_owner())
