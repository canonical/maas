#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasserver.enum import INTERFACE_TYPE
from maasserver.mac_normalization import (
    DUPLICATE_MAC_NOTIFICATION_IDENT,
    find_duplicate_mac_addresses,
    sync_duplicate_mac_address_notification,
)
from maasserver.models import Interface, Notification
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


def _set_raw_mac(interface, mac_address):
    """Store a MAC verbatim, bypassing model normalization on save."""
    Interface.objects.filter(id=interface.id).update(mac_address=mac_address)


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

    def test_ignores_same_mac_on_different_nodes(self):
        # The uniqueness constraint is scoped per node_config, so the same
        # physical MAC stored in different formats on different nodes does not
        # bypass any check.
        node1 = factory.make_Node()
        node2 = factory.make_Node()
        if1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node1)
        if2 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node2)
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


class TestSyncDuplicateMacAddressNotification(MAASServerTestCase):
    def test_creates_notification_when_duplicates_exist(self):
        node = factory.make_Node()
        if1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        if2 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        _set_raw_mac(if1, "aa:bb:cc:dd:ee:ff")
        _set_raw_mac(if2, "AA:BB:CC:DD:EE:FF")

        sync_duplicate_mac_address_notification()

        notification = Notification.objects.get(
            ident=DUPLICATE_MAC_NOTIFICATION_IDENT
        )
        self.assertEqual("warning", notification.category)
        self.assertTrue(notification.admins)
        self.assertFalse(notification.dismissable)

    def test_clears_notification_when_no_duplicates(self):
        Notification.objects.create_warning_for_admins(
            "stale",
            ident=DUPLICATE_MAC_NOTIFICATION_IDENT,
            dismissable=False,
        )

        sync_duplicate_mac_address_notification()

        self.assertFalse(
            Notification.objects.filter(
                ident=DUPLICATE_MAC_NOTIFICATION_IDENT
            ).exists()
        )
