# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Python wrapper around the `omshell` utility which amends objects
inside the DHCP server.
"""


import base64
import secrets
from subprocess import PIPE, Popen
from textwrap import dedent

from provisioningserver.logger import get_maas_logger, LegacyLogger
from provisioningserver.utils import typed
from provisioningserver.utils.shell import ExternalProcessError

log = LegacyLogger()
maaslog = get_maas_logger("dhcp.omshell")


def generate_omapi_key():
    """Generate a HMAC-MD5 key.

    :return: The shared key suitable for OMAPI access.
    :type: string
    """
    return base64.b64encode(secrets.token_bytes(64)).decode("ascii")


class Omshell:
    """Wrap up the omshell utility in Python.

    'omshell' is an external executable that communicates with a DHCP daemon
    and manipulates its objects.  This class wraps up the commands necessary
    to add and remove host maps (MAC to IP).

    :param server_address: The address for the DHCP server (ip or hostname)
    :param shared_key: An HMAC-MD5 key.
        It must match the key set in the DHCP server's config which looks
        like this:

        omapi-port 7911;
        key omapi_key {
            algorithm HMAC-MD5;
            secret "XXXXXXXXX"; #<-The output from the generated key above.
        };
        omapi-key omapi_key;
    """

    def __init__(self, server_address, shared_key, ipv6=False):
        self.server_address = server_address
        self.shared_key = shared_key
        self.ipv6 = ipv6
        self.command = ["omshell"]
        if ipv6 is True:
            self.server_port = 7912
        else:
            self.server_port = 7911

    def _run(self, stdin):
        proc = Popen(self.command, stdin=PIPE, stdout=PIPE)
        stdout, stderr = proc.communicate(stdin)
        if proc.poll() != 0:
            raise ExternalProcessError(proc.returncode, self.command, stdout)
        return proc.returncode, stdout

    def try_connection(self):
        # Don't pass the omapi_key as its not needed to just try to connect.
        stdin = dedent(
            """\
            server {self.server_address}
            port {self.server_port}
            connect
            """
        )
        stdin = stdin.format(self=self)

        returncode, output = self._run(stdin.encode("utf-8"))

        # If the omshell worked, the last line should reference a null
        # object.  We need to strip blanks, newlines and '>' characters
        # for this to work.
        lines = output.strip(b"\n >").splitlines()
        try:
            last_line = lines[-1]
        except IndexError:
            last_line = ""
        if b"obj: <null" in last_line:
            return True
        else:
            return False

    @typed
    def create(self, ip_address: str, mac_address: str):
        # The "name" is not a host name; it's an identifier used within
        # the DHCP server. We use the MAC address. Prior to 1.9, MAAS used
        # the IPs as the key but changing to using MAC addresses allows the
        # DHCP service to give all the NICs of a bond the same IP address.
        # The only caveat of this change is that the remove() method in this
        # class has to be able to deal with legacy host mappings (using IP as
        # the key) and new host mappings (using the MAC as the key).
        log.debug(
            "Creating host mapping {mac}->{ip}", mac=mac_address, ip=ip_address
        )
        name = mac_address.replace(":", "-")
        stdin = dedent(
            """\
            server {self.server_address}
            port {self.server_port}
            key omapi_key {self.shared_key}
            connect
            new host
            set ip-address = {ip_address}
            set hardware-address = {mac_address}
            set hardware-type = 1
            set name = "{name}"
            create
            """
        )
        stdin = stdin.format(
            self=self,
            ip_address=ip_address,
            mac_address=mac_address,
            name=name,
        )

        returncode, output = self._run(stdin.encode("utf-8"))
        # If the call to omshell doesn't result in output containing the
        # magic string 'hardware-type' then we can be reasonably sure
        # that the 'create' command failed.  Unfortunately there's no
        # other output like "successful" to check so this is the best we
        # can do.
        if b"hardware-type" in output:
            # Success.
            pass
        elif b"can't open object: I/O error" in output:
            # Host map already existed.  Treat as success.
            pass
        else:
            raise ExternalProcessError(returncode, self.command, output)

    @typed
    def modify(self, ip_address: str, mac_address: str):
        # The "name" is not a host name; it's an identifier used within
        # the DHCP server. We use the MAC address. Prior to 1.9, MAAS used
        # the IPs as the key but changing to using MAC addresses allows the
        # DHCP service to give all the NICs of a bond the same IP address.
        # The only caveat of this change is that the remove() method in this
        # class has to be able to deal with legacy host mappings (using IP as
        # the key) and new host mappings (using the MAC as the key).
        log.debug(
            "Modifing host mapping {mac}->{ip}", mac=mac_address, ip=ip_address
        )
        name = mac_address.replace(":", "-")
        stdin = dedent(
            """\
            server {self.server_address}
            key omapi_key {self.shared_key}
            connect
            new host
            set name = "{name}"
            open
            set ip-address = {ip_address}
            set hardware-address = {mac_address}
            set hardware-type = 1
            update
            """
        )
        stdin = stdin.format(
            self=self,
            ip_address=ip_address,
            mac_address=mac_address,
            name=name,
        )

        returncode, output = self._run(stdin.encode("utf-8"))
        # If the call to omshell doesn't result in output containing the
        # magic string 'hardware-type' then we can be reasonably sure
        # that the 'update' command failed.  Unfortunately there's no
        # other output like "successful" to check so this is the best we
        # can do.
        if b"hardware-type" in output:
            # Success.
            pass
        else:
            raise ExternalProcessError(returncode, self.command, output)

    @typed
    def remove(self, mac_address: str):
        # The "name" is not a host name; it's an identifier used within
        # the DHCP server. We use the MAC address. Prior to 1.9, MAAS using
        # the IPs as the key but changing to using MAC addresses allows the
        # DHCP service to give all the NICs of a bond the same IP address.
        # The only caveat of this change is that the remove() method needs
        # to be able to deal with legacy host mappings (using IP as
        # the key) and new host mappings (using the MAC as the key).
        # This is achieved by sending both the IP and the MAC: one of them will
        # be the key for the mapping (it will be the IP if the record was
        # created with by an old version of MAAS and the MAC otherwise).
        log.debug("Removing host mapping key={mac}", mac=mac_address)
        mac_address = mac_address.replace(":", "-")
        stdin = dedent(
            """\
            server {self.server_address}
            port {self.server_port}
            key omapi_key {self.shared_key}
            connect
            new host
            set name = "{mac_address}"
            open
            remove
            """
        )
        stdin = stdin.format(self=self, mac_address=mac_address)

        returncode, output = self._run(stdin.encode("utf-8"))

        # If the omshell worked, the last line should reference a null
        # object.  We need to strip blanks, newlines and '>' characters
        # for this to work.
        lines = output.strip(b"\n >").splitlines()
        try:
            last_line = lines[-1]
        except IndexError:
            last_line = ""
        if b"obj: <null" in last_line:
            # Success.
            pass
        elif b"can't open object: not found" in output:
            # It was already removed. Consider success.
            pass
        else:
            raise ExternalProcessError(returncode, self.command, output)

    @typed
    def nullify_lease(self, ip_address: str):
        """Reset an existing lease so it's no longer valid.

        You can't delete leases with omshell, so we're setting the expiry
        timestamp to the epoch instead.
        """
        stdin = dedent(
            """\
            server {self.server_address}
            port {self.server_port}
            key omapi_key {self.shared_key}
            connect
            new lease
            set ip-address = {ip_address}
            open
            set ends = 00:00:00:00
            update
            """
        )
        stdin = stdin.format(self=self, ip_address=ip_address)

        returncode, output = self._run(stdin.encode("utf-8"))

        if b"can't open object: not found" in output:
            # Consider nonexistent leases a success.
            return None

        # Catching "invalid" is a bit like catching a bare exception
        # but omshell is so esoteric that this is probably quite safe.
        # If the update succeeded, "ends = 00:00:00:00" will most certainly
        # be in the output.  If it's not, there's been a failure.
        if b"invalid" not in output and b"\nends = 00:00:00:00" in output:
            return None

        raise ExternalProcessError(returncode, self.command, output)
