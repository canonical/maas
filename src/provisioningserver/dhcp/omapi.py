import base64
import secrets

from pypureomapi import (
    Omapi,
    OMAPI_OP_STATUS,
    OMAPI_OP_UPDATE,
    OmapiError,
    OmapiMessage,
    pack_ip,
)


def generate_omapi_key() -> str:
    """Generate a base64-encoded key to use for OMAPI access."""
    return base64.b64encode(secrets.token_bytes(64)).decode("ascii")


class OmapiClient:
    """Client for the DHCP OMAPI."""

    def __init__(self, omapi_key: str, ipv6: bool = False):
        self._omapi = Omapi(
            "127.0.0.1",
            7912 if ipv6 else 7911,
            b"omapi_key",
            omapi_key.encode("ascii"),
        )

    def add_host(self, mac: str, ip: str):
        """Add a host mapping for a MAC."""
        name = self._name_from_mac(mac)
        self._omapi.add_host_supersede(ip, mac, name)

    def del_host(self, mac: str):
        """Remove a host mapping for a MAC."""
        self._omapi.del_host(mac)

    def update_host(self, mac: str, ip: str):
        """Update a host mapping for a MAC."""
        name = self._name_from_mac(mac)
        msg = OmapiMessage.open(b"host")
        msg.update_object({b"name": name})
        resp = self._omapi.query_server(msg)
        if resp.opcode != OMAPI_OP_UPDATE:
            raise OmapiError(f"Host not found: {name.decode('ascii')}")
        msg = OmapiMessage.update(resp.handle)
        msg.update_object({b"ip-address": pack_ip(ip)})
        resp = self._omapi.query_server(msg)
        if resp.opcode != OMAPI_OP_STATUS:
            raise OmapiError(
                f"Updating IP for host {name.decode('ascii')} to {ip} failed"
            )

    def _name_from_mac(self, mac: str) -> bytes:
        return mac.replace(":", "-").encode("ascii")
