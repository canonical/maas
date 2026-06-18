#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from django.db import connection

from maasserver.enum import INTERFACE_TYPE
from maasserver.mac_duplicates import find_duplicate_mac_addresses
from maasserver.models.nodeconfig import NODE_CONFIG_TYPE
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


def _set_raw_mac(interface, mac_address):
    """Store a MAC verbatim, bypassing model normalization on save.

    Uses raw SQL because ``MACAddressField`` normalizes values on every ORM
    write path (including ``QuerySet.update()``), which would otherwise
    prevent the inconsistently formatted duplicates these tests rely on.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE maasserver_interface SET mac_address = %s WHERE id = %s",
            [mac_address, interface.id],
        )


class TestFindDuplicateMacAddresses(MAASServerTestCase):
    def test_returns_empty_when_no_duplicates(self):
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, mac_address="aa:bb:cc:dd:ee:ff"
        )
        self.assertEqual([], find_duplicate_mac_addresses())

    def test_detects_macs_stored_in_different_format(self):
        node = factory.make_Node()
        if1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        if2 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        _set_raw_mac(if1, "aa:bb:cc:dd:ee:ff")
        _set_raw_mac(if2, "AA:BB:CC:DD:EE:FF")

        self.assertEqual(["aa:bb:cc:dd:ee:ff"], find_duplicate_mac_addresses())

    def test_detects_same_mac_on_different_nodes(self):
        # MAAS forbids the same physical MAC on different nodes, so a pair
        # stored in different formats across nodes bypasses that check and must
        # be reported.
        node1 = factory.make_Node()
        node2 = factory.make_Node()
        if1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node1)
        if2 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node2)
        _set_raw_mac(if1, "aa:bb:cc:dd:ee:ff")
        _set_raw_mac(if2, "AA:BB:CC:DD:EE:FF")

        self.assertEqual(["aa:bb:cc:dd:ee:ff"], find_duplicate_mac_addresses())

    def test_detects_identical_mac_on_different_nodes(self):
        # Two physical interfaces on different nodes that share an identical
        # stored MAC also bypass the cross-node uniqueness check. The 3.8
        # migration aborts the upgrade on these, so they must be reported too.
        node1 = factory.make_Node()
        node2 = factory.make_Node()
        if1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node1)
        if2 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node2)
        _set_raw_mac(if1, "aa:bb:cc:dd:ee:ff")
        _set_raw_mac(if2, "aa:bb:cc:dd:ee:ff")

        self.assertEqual(["aa:bb:cc:dd:ee:ff"], find_duplicate_mac_addresses())

    def test_ignores_same_mac_across_node_configs_of_same_node(self):
        # The same physical MAC may legitimately appear on different
        # node_configs of the same node, so it must not be reported even when
        # the stored values differ in case.
        node = factory.make_Node()
        other_config = factory.make_NodeConfig(
            node=node, name=NODE_CONFIG_TYPE.DEPLOYMENT
        )
        if1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node_config=node.current_config
        )
        if2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node_config=other_config
        )
        _set_raw_mac(if1, "aa:bb:cc:dd:ee:ff")
        _set_raw_mac(if2, "AA:BB:CC:DD:EE:FF")

        self.assertEqual([], find_duplicate_mac_addresses())

    def test_ignores_bond_sharing_child_mac_address(self):
        # Bonds legitimately reuse a child interface's MAC address; this is a
        # valid use case and must not be reported even when the stored values
        # differ in case.
        node = factory.make_Node()
        parent = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        bond = factory.make_Interface(
            INTERFACE_TYPE.BOND, node=node, parents=[parent]
        )
        _set_raw_mac(parent, "aa:bb:cc:dd:ee:ff")
        _set_raw_mac(bond, "AA:BB:CC:DD:EE:FF")

        self.assertEqual([], find_duplicate_mac_addresses())
