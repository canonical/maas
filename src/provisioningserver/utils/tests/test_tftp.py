# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for ``provisioningserver.utils.tftp``."""


from twisted.python.context import call

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.utils import tftp


class TestAddressFunctions(MAASTestCase):
    scenarios = (
        (
            "get_local_address",
            {"get_address": tftp.get_local_address, "context_key": "local"},
        ),
        (
            "get_remote_address",
            {"get_address": tftp.get_remote_address, "context_key": "remote"},
        ),
    )

    def test_returns_None_None_tuple_when_not_set(self):
        self.assertEqual((None, None), self.get_address())

    def test_returns_host_port_tuple_when_set(self):
        host, port = factory.make_hostname(), factory.pick_port()
        context = {self.context_key: (host, port)}
        self.assertEqual((host, port), call(context, self.get_address))

    def test_returns_host_port_tuple_even_when_set_longer(self):
        # Only the first two elements from the context's value are used.
        host, port = factory.make_hostname(), factory.pick_port()
        context = {self.context_key: (host, port, factory.make_name("thing"))}
        self.assertEqual((host, port), call(context, self.get_address))

    def test_blows_up_when_tuple_has_no_elements(self):
        context = {self.context_key: ()}
        self.assertRaises(AssertionError, call, context, self.get_address)

    def test_blows_up_when_tuple_has_one_element(self):
        context = {self.context_key: (factory.make_hostname(),)}
        self.assertRaises(AssertionError, call, context, self.get_address)
