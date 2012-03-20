# Copyright 2008 (c) Pierre Duquesne <stackp@online.fr>
# Copyright 2012 Canonical Ltd.
# This software is licensed under the GNU Affero General Public
# License version 3 (see the file LICENSE).
# Example code taken from http://stackp.online.fr/?p=35

import avahi
import dbus

__all__ = [
    "ZeroconfService",
    ]


class ZeroconfService:
    """A simple class to publish a network service with zeroconf using avahi.
    """

    def __init__(self, name, port, stype="_http._tcp",
                 domain="", host="", text=""):
        """Create an object that can publish a service over Avahi.

        :param name: The name of the service to be published.
        :param port: The port number where it's published.
        :param stype: The service type string.
        """
        self.name = name
        self.stype = stype
        self.domain = domain
        self.host = host
        self.port = port
        self.text = text

    def publish(self):
        """Publish the service through Avahi."""
        bus = dbus.SystemBus()
        server = dbus.Interface(
             bus.get_object(avahi.DBUS_NAME, avahi.DBUS_PATH_SERVER),
             avahi.DBUS_INTERFACE_SERVER)

        group = dbus.Interface(
            bus.get_object(avahi.DBUS_NAME, server.EntryGroupNew()),
            avahi.DBUS_INTERFACE_ENTRY_GROUP)

        group.AddService(
            avahi.IF_UNSPEC, avahi.PROTO_UNSPEC, dbus.UInt32(0),
            self.name, self.stype, self.domain, self.host,
            dbus.UInt16(self.port), self.text)

        group.Commit()
        self.group = group

    def unpublish(self):
        """Unpublish the service through Avahi."""
        self.group.Reset()


if __name__ == "__main__":
    service = ZeroconfService(name="TestService", port=3000)
    service.publish()
    raw_input("Press any key to unpublish the service ")
    service.unpublish()
