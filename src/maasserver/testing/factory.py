import string
import random

from maasserver.models import Node, MACAddress


class Factory():

    def getRandomString(self, size):
        return "".join(
            random.choice(string.letters+string.digits)
            for x in xrange(size))

    def make_node(self, hostname='', set_hostname=False, status=None,
                  **kwargs):
        # hostname=None is a valid value, hence the set_hostname trick.
        if hostname is '' and set_hostname:
            hostname = self.getRandomString(255)
        if status is None:
            status = u'NEW'
        node = Node(hostname=hostname, status=status, **kwargs)
        node.save()
        return node

    def make_mac_address(self, address):
        """Create a MAC address."""
        node = Node()
        node.save()
        mac = MACAddress(mac_address=address, node=node)
        return mac


# Create factory singleton.
factory = Factory()
