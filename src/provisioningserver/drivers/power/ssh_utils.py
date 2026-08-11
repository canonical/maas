#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
"""SSH helpers for power drivers, FIPS-aware."""

from __future__ import annotations

import logging
from typing import Any, Callable

from paramiko import (
    AutoAddPolicy,
    MissingHostKeyPolicy,
    RejectPolicy,
    SSHClient,
)
from twisted.internet.threads import blockingCallFromThread

from maascommon.fips import FIPS_SSH_CONFIG, is_fips_enabled
from maascommon.logging.security import (
    log_fips_crypto_error,
    log_fips_ssh_authentication,
)

log = logging.getLogger("maas.fips")

# Lazy-resolved so tests can override before first RPC, and so this
# module doesn't pull paramiko transitively via ``provisioningserver.rpc``.
_rpc_client_factory: Callable[[], Any] | None = None
_rpc_command: Any | None = None


def get_fips_transport_options() -> dict[str, Any]:
    """Return ``disabled_algorithms`` kwargs for ``SSHClient.connect`` when FIPS is active.

    paramiko blocks any algorithm absent from its ``Transport._preferred_*``
    lists, so the disable-set is the complement of :data:`FIPS_SSH_CONFIG`.
    Returns an empty dict on non-FIPS hosts.
    """
    if not is_fips_enabled():
        return {}

    # Lazy: paramiko.Transport is only needed when FIPS is on.
    from paramiko.transport import Transport

    return {
        "disabled_algorithms": {
            "ciphers": sorted(
                set(Transport._preferred_ciphers)
                - set(FIPS_SSH_CONFIG.ciphers)
            ),
            "kex": sorted(
                set(Transport._preferred_kex) - set(FIPS_SSH_CONFIG.kex)
            ),
            "macs": sorted(
                set(Transport._preferred_macs) - set(FIPS_SSH_CONFIG.macs)
            ),
            "keys": sorted(
                set(Transport._preferred_keys) - set(FIPS_SSH_CONFIG.key_types)
            ),
        }
    }


class TrustedHostKeyPolicy(MissingHostKeyPolicy):
    """paramiko host-key policy that verifies keys via the MAAS region RPC.

    Set ``fail_open=True`` to accept unknown keys without an RPC round-trip;
    only use this in contexts where region RPC is unavailable (e.g. the
    region controller itself).
    """

    def __init__(self, fail_open: bool = False) -> None:
        self._fail_open = fail_open

    def missing_host_key(self, client, hostname, key):  # type: ignore[override]
        key_type = key.get_name()
        key_b64 = key.get_base64()
        if self._lookup_trusted_key(hostname, key_type, key_b64):
            client._host_keys.add(hostname, key_type, key)
            return
        log_fips_crypto_error(
            operation="ssh_host_key_verify",
            error="untrusted host key",
            algorithm=key.get_name(),
            peer=hostname,
        )
        raise RejectPolicy().missing_host_key(client, hostname, key)

    def _lookup_trusted_key(
        self, hostname: str, key_type: str, key_b64: str
    ) -> bool:
        """Return True iff the host key is trusted per the MAAS region.

        Called synchronously inside paramiko's SSH handshake (a
        ``deferToThread`` thread), so the Twisted RPC is dispatched via
        ``blockingCallFromThread``. Any RPC failure returns False (fail-secure);
        ``fail_open`` returns True without RPC.
        """
        if self._fail_open:
            return True
        global _rpc_client_factory, _rpc_command
        if _rpc_client_factory is None:
            from provisioningserver.rpc import getRegionClient
            from provisioningserver.rpc.region import VerifyTrustedSshHostKey

            _rpc_client_factory = getRegionClient
            _rpc_command = VerifyTrustedSshHostKey
        try:
            from twisted.internet import reactor

            rpc_client = _rpc_client_factory()
            result = blockingCallFromThread(
                reactor,
                rpc_client,
                _rpc_command,
                host=hostname,
                key_type=key_type,
                public_key=key_b64,
            )
            return bool(result.get("verified", False))
        except Exception as exc:
            log.warning(
                "TrustedHostKeyPolicy: RPC lookup failed for %s (%s); "
                "rejecting key (fail-secure). Error: %s",
                hostname,
                key_type,
                exc,
            )
            return False


def make_ssh_client() -> SSHClient:
    """Return an ``SSHClient`` with the FIPS-appropriate host-key policy."""
    client = SSHClient()
    if is_fips_enabled():
        client.set_missing_host_key_policy(TrustedHostKeyPolicy())
    else:
        client.set_missing_host_key_policy(AutoAddPolicy())
    return client


def connect_ssh_client(
    client: SSHClient,
    power_address: str,
    power_user: str,
    power_pass: str,
) -> None:
    """Call ``SSHClient.connect`` with FIPS transport options merged in when active."""
    client.connect(
        power_address,
        username=power_user,
        password=power_pass,
        **get_fips_transport_options(),
    )
    if is_fips_enabled():
        transport = client.get_transport()
        if transport is not None:
            host_key = transport.get_remote_server_key()
            key_type = host_key.get_name() if host_key else "unknown"
            kex_engine = getattr(transport, "kex_engine", None)
            kex = getattr(kex_engine, "name", "unknown")
            cipher = transport.local_cipher or "unknown"
            mac = transport.local_mac or "unknown"
        else:
            key_type = kex = cipher = mac = "unknown"
        log_fips_ssh_authentication(
            key_type=key_type,
            kex=kex,
            cipher=cipher,
            mac=mac,
            peer=power_address,
            result="success",
        )
