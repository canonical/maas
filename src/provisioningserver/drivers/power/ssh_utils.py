#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
"""SSH helpers for power drivers, FIPS-aware."""

from __future__ import annotations

import json
import logging
import os
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

MAAS_TRUSTED_SSH_HOST_KEYS_ENV = "MAAS_TRUSTED_SSH_HOST_KEYS"

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
    """paramiko host-key policy that verifies keys via env var or MAAS region RPC.

    Checks the ``MAAS_TRUSTED_SSH_HOST_KEYS`` environment variable first
    (cheap, local). Falls back to RPC when the env var is absent.
    Set ``fail_open=True`` to accept unknown keys without any lookup;
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
        """Return True iff the host key is trusted.

        Tries the ``MAAS_TRUSTED_SSH_HOST_KEYS`` environment variable first
        (cheap, local memory — available when running in the ``maas-power``
        subprocess spawned by the agent). Falls back to RPC (network
        round-trip — available when running in rackd). ``fail_open`` returns
        True without any lookup.
        """
        if self._fail_open:
            return True
        env_result = self._lookup_trusted_key_via_env(
            hostname, key_type, key_b64
        )
        if env_result is not None:
            return env_result
        try:
            return self._lookup_trusted_key_via_rpc(
                hostname, key_type, key_b64
            )
        except Exception as exc:
            log.debug(
                "TrustedHostKeyPolicy: RPC lookup failed for %s (%s); "
                "rejecting key (fail-secure). Error: %s",
                hostname,
                key_type,
                exc,
            )
            return False

    def _lookup_trusted_key_via_rpc(
        self, hostname: str, key_type: str, key_b64: str
    ) -> bool:
        """Return True iff the host key is trusted via the MAAS region RPC."""
        global _rpc_client_factory, _rpc_command
        if _rpc_client_factory is None:
            from provisioningserver.rpc import getRegionClient
            from provisioningserver.rpc.region import VerifyTrustedSshHostKey

            _rpc_client_factory = getRegionClient
            _rpc_command = VerifyTrustedSshHostKey
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

    @staticmethod
    def _lookup_trusted_key_via_env(
        hostname: str, key_type: str, key_b64: str
    ) -> bool | None:
        """Return True if the host key matches one in the env var.

        Returns ``None`` when the env var is absent (caller should fall back
        to RPC).  Returns ``True`` when the key is found, ``False`` when the
        env var is present but the key is not in it (definitive rejection).
        """
        raw = os.environ.get(MAAS_TRUSTED_SSH_HOST_KEYS_ENV)
        if not raw:
            return None
        try:
            keys = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            log.warning(
                "TrustedHostKeyPolicy: failed to parse %s env var; "
                "rejecting key for %s (fail-secure).",
                MAAS_TRUSTED_SSH_HOST_KEYS_ENV,
                hostname,
            )
            return False
        if not isinstance(keys, list):
            log.warning(
                "TrustedHostKeyPolicy: %s env var is not a JSON list; "
                "rejecting key for %s (fail-secure).",
                MAAS_TRUSTED_SSH_HOST_KEYS_ENV,
                hostname,
            )
            return False
        for entry in keys:
            if (
                entry.get("host") == hostname
                and entry.get("key_type") == key_type
                and entry.get("public_key") == key_b64
            ):
                return True
        log.warning(
            "TrustedHostKeyPolicy: key for %s (%s) not found in %s; "
            "rejecting (fail-secure).",
            hostname,
            key_type,
            MAAS_TRUSTED_SSH_HOST_KEYS_ENV,
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
