# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test for :py:mod:`maasserver.clusterrpc.power`."""

__all__ = []

from maasserver.clusterrpc.power import (
    power_driver_check,
    power_off_node,
    power_on_node,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledOnceWith
from mock import Mock
from provisioningserver.rpc.cluster import (
    PowerDriverCheck,
    PowerOff,
    PowerOn,
)
from provisioningserver.utils.twisted import reactor_sync


class TestPowerNode(MAASServerTestCase):
    """Tests for `power_on_node` and `power_off_node`."""

    scenarios = (
        ("PowerOn", {"power_func": power_on_node, "command": PowerOn}),
        ("PowerOff", {"power_func": power_off_node, "command": PowerOff}),
    )

    def test__powers_single_node(self):
        node = factory.make_Node()
        client = Mock()

        # We're not doing any IO via the reactor so we sync with it only so
        # that this becomes the IO thread, making @asynchronous transparent.
        with reactor_sync():
            self.power_func(
                client, node.system_id, node.hostname,
                node.get_effective_power_info())

        power_info = node.get_effective_power_info()
        self.assertThat(
            client,
            MockCalledOnceWith(
                self.command, system_id=node.system_id, hostname=node.hostname,
                power_type=power_info.power_type,
                context=power_info.power_parameters,
            ))


class TestPowerDriverCheck(MAASServerTestCase):
    """Tests for `power_driver_check`."""

    def test__handled(self):
        node = factory.make_Node()
        power_info = node.get_effective_power_info()
        client = Mock()

        # We're not doing any IO via the reactor so we sync with it only so
        # that this becomes the IO thread, making @asynchronous transparent.
        with reactor_sync():
            power_driver_check(
                client, power_info.power_type)

        self.assertThat(
            client,
            MockCalledOnceWith(
                PowerDriverCheck, power_type=power_info.power_type
            ))
