# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Node IP/MAC mappings as leased from the workers' DHCP servers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'DHCPLease',
    ]


from django.db import connection
from django.db.models import (
    ForeignKey,
    IPAddressField,
    Manager,
    Model,
    )
from maasserver import DefaultMeta
from maasserver.fields import MACAddressField
from maasserver.models.cleansave import CleanSave


class DHCPLeaseManager(Manager):
    """Utility that manages :class:`DHCPLease` objects.

    This will be a large and busy part of the database.  Try to perform
    operations in bulk, using this manager class, where at all possible.
    """

    def _delete_obsolete_leases(self, nodegroup, current_leases):
        """Delete leases for `nodegroup` that aren't in `current_leases`."""
        cursor = connection.cursor()
        clauses = ["nodegroup_id = %s" % nodegroup.id]
        if len(current_leases) > 0:
            leases = tuple(current_leases.items())
        if len(current_leases) == 0:
            pass
        elif len(current_leases) == 1:
            clauses.append(cursor.mogrify("(ip, mac) <> %s", leases))
        else:
            clauses.append(cursor.mogrify("(ip, mac) NOT IN %s", [leases]))
        cursor.execute(
            "DELETE FROM maasserver_dhcplease WHERE %s"
            % " AND ".join(clauses)),

    def _get_leased_ips(self, nodegroup):
        """Query the currently leased IP addresses for `nodegroup`."""
        cursor = connection.cursor()
        cursor.execute(
            "SELECT ip FROM maasserver_dhcplease WHERE nodegroup_id = %s"
            % nodegroup.id)
        return frozenset(ip for ip, in cursor.fetchall())

    def _add_missing_leases(self, nodegroup, leases):
        """Add items from `leases` that aren't in the database yet.

        This is assumed to be run right after _delete_obsolete_leases,
        so that a lease from `leases` is in the database if and only if
        `nodegroup` has a DHCPLease with the same `ip` field.  There
        can't be any DHCPLease entries with the same `ip` as in `leases`
        but a different `mac`.
        """
        leased_ips = self._get_leased_ips(nodegroup)
        new_leases = tuple(
            (nodegroup.id, ip, mac)
            for ip, mac in leases.items() if ip not in leased_ips)
        if len(new_leases) > 0:
            cursor = connection.cursor()
            new_tuples = ", ".join(
                cursor.mogrify("%s", [lease]) for lease in new_leases)
            cursor.execute("""
                INSERT INTO maasserver_dhcplease (nodegroup_id, ip, mac)
                VALUES %s
                """ % new_tuples)

    def update_leases(self, nodegroup, leases):
        """Refresh our knowledge of a node group's IP mappings.

        This deletes entries that are no longer current, adds new ones,
        and updates or replaces ones that have changed.

        :param nodegroup: The node group that these updates are for.
        :param leases: A dict describing all current IP/MAC mappings as
            managed by the node group's DHCP server.  Keys are IP
            addresses, values are MAC addresses.  Any :class:`DHCPLease`
            entries for `nodegroup` that are not in `leases` will be
            deleted.
        """
        self._delete_obsolete_leases(nodegroup, leases)
        self._add_missing_leases(nodegroup, leases)

    def get_hostname_ip_mapping(self, nodegroup):
        """Return a mapping {hostnames -> ips} for the currently leased
        IP addresses for the nodes in `nodegroup`.

        This will consider only the first interface (i.e. the first
        MAC Address) associated with each node withing the given
        `nodegroup`.
        """
        cursor = connection.cursor()
        # The subquery fetches the IDs of the first MAC Address for
        # all the nodes in this nodegroup.
        # Then the main query returns the hostname -> ip mapping for
        # these MAC Addresses.
        cursor.execute("""
        SELECT node.hostname, lease.ip
        FROM maasserver_macaddress as mac,
             maasserver_node as node,
             maasserver_dhcplease as lease
        WHERE mac.id IN (
            SELECT DISTINCT ON (node_id) mac.id
            FROM maasserver_macaddress as mac,
                 maasserver_node as node
            WHERE node.nodegroup_id = %s AND mac.node_id = node.id
            ORDER BY node_id, mac.id
        )
        AND mac.node_id = node.id
        AND mac.mac_address = lease.mac
        AND lease.nodegroup_id = %s
        """, (nodegroup.id, nodegroup.id))
        return dict(cursor.fetchall())


class DHCPLease(CleanSave, Model):
    """A known mapping of an IP address to a MAC address.

    These correspond to the latest-known DHCP leases handed out to nodes
    (or potential nodes -- they may not have been enlisted yet!) by the
    node group worker's DHCP server.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = DHCPLeaseManager()

    nodegroup = ForeignKey('maasserver.NodeGroup', null=False, editable=False)
    ip = IPAddressField(null=False, editable=False, unique=True)
    mac = MACAddressField(null=False, editable=False, unique=False)

    def __unicode__(self):
        return "%s->%s" % (self.ip, self.mac)
