# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Migration to populate new Interface to IP table.

WARNING: Although these methods will become obsolete very quickly, they
cannot be removed, since they are used by the
0164_move_ip_links_to_interface_table DataMigration.
(changing them might also be futile unless a customer restores from a backup,
since any bugs that occur will have already occurred, and this code will not be
executed again.)

Note: Each helper must have its dependencies on any model classes injected,
since the migration environment is a skeletal replication of the 'real'
database model. So each function takes as parameters the model classes it
requires. Importing from the model is not allowed here. (but the unit tests
do it, to ensure that the migrations meet validation requirements.)
"""


def _migrate_links_forward(MACAddress, Interface):
    """Using the links from MACAddress to StaticIPAddress, create the link
    from each StaticIPAddress to its new Interface (which was created in a
    previous migration).
    """
    for mac in MACAddress.objects.all():
        # In a sense, we're just guessing here. Grab the first interface
        # with a matching MAC. It should be the correct one, since
        # we only created PhyhsicalInterfaces when we migrated.
        ifaces = Interface.objects.filter(mac=mac).order_by("id")
        # XXX can we log this?
        # if len(ifaces) > 1:
        #     print("More than one interface found for mac=%s" % mac)
        iface = ifaces.first()
        for ip in mac.ip_addresses.all():
            iface.ip_addresses.add(ip)
