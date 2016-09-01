# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `metadataserver.vendor_data`."""

__all__ = []

from maasserver.models.config import Config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from metadataserver.vendor_data import (
    generate_ntp_configuration,
    generate_system_info,
    get_vendor_data,
)
from testtools.matchers import (
    ContainsDict,
    Equals,
    Is,
    IsInstance,
    KeysEqual,
    MatchesDict,
)


class TestGetVendorData(MAASServerTestCase):
    """Tests for `get_vendor_data`."""

    def test_returns_dict(self):
        node = factory.make_Node()
        self.assertThat(get_vendor_data(node), IsInstance(dict))

    def test_includes_system_information(self):
        node = factory.make_Node(owner=factory.make_User())
        vendor_data = get_vendor_data(node)
        self.assertThat(vendor_data, ContainsDict({
            "system_info": MatchesDict({
                "default_user": KeysEqual("name", "gecos"),
            }),
        }))

    def test_includes_ntp_server_information(self):
        Config.objects.set_config("ntp_servers", "foo bar")
        node = factory.make_Node()
        vendor_data = get_vendor_data(node)
        self.assertThat(vendor_data, ContainsDict({
            "ntp": Equals({
                "servers": ["bar", "foo"],
            }),
        }))


class TestGenerateSystemInfo(MAASServerTestCase):
    """Tests for `generate_system_info`."""

    def test_yields_nothing_when_node_has_no_owner(self):
        node = factory.make_Node()
        self.assertThat(node.owner, Is(None))
        configuration = generate_system_info(node)
        self.assertThat(dict(configuration), Equals({}))

    def test_yields_basic_system_info_when_node_is_owned(self):
        owner = factory.make_User()
        owner.first_name = "First"
        owner.last_name = "Last"
        owner.save()
        node = factory.make_Node(owner=owner)
        configuration = generate_system_info(node)
        self.assertThat(dict(configuration), Equals({
            "system_info": {
                "default_user": {
                    "name": owner.username,
                    "gecos": "First Last,,,,",
                },
            },
        }))


class TestGenerateNTPConfiguration(MAASServerTestCase):
    """Tests for `generate_ntp_configuration`."""

    def test_yields_nothing_when_no_ntp_servers_are_defined(self):
        Config.objects.set_config("ntp_servers", "")
        configuration = generate_ntp_configuration()
        self.assertThat(dict(configuration), Equals({}))

    def test_yields_all_ntp_servers_when_defined(self):
        ntp_servers = factory.make_hostname(), factory.make_hostname()
        Config.objects.set_config("ntp_servers", " ".join(ntp_servers))
        configuration = generate_ntp_configuration()
        self.assertThat(dict(configuration), Equals({
            "ntp": {
                "servers": sorted(ntp_servers),
            },
        }))
