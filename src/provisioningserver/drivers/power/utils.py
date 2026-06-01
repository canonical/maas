# Copyright 2019-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helpers for MAAS power drivers."""

from collections.abc import Callable

from OpenSSL import SSL as _SSL
from paramiko import AutoAddPolicy, RejectPolicy, SSHClient, SSHException
import structlog
from twisted.internet._sslverify import (
    ClientTLSOptions,
    OpenSSLCertificateOptions,
)
from twisted.internet.ssl import platformTrust
from twisted.web.client import BrowserLikePolicyForHTTPS

from maascommon.fips import get_fips_ssh_config, is_fips_enabled
from maascommon.logging.security import (
    FIPS_CRYPTO_ERROR,
    FIPS_SSH_AUTH,
    FIPS_TLS_HANDSHAKE,
)

logger = structlog.getLogger()


def _make_fips_tls_info_callback(
    peer: str,
) -> Callable[[object, int, int], None]:
    """Return an OpenSSL info callback that logs FIPS_TLS_HANDSHAKE.

    The callback fires on every SSL state change; we only emit a structured
    log entry when the handshake has completed (``SSL_CB_HANDSHAKE_DONE``).
    """

    def _callback(conn: object, where: int, ret: int) -> None:  # noqa: ARG001
        if where & _SSL.SSL_CB_HANDSHAKE_DONE:
            try:
                cipher_name = conn.get_cipher_name()
                protocol = conn.get_protocol_version_name()
                peer_cert = conn.get_peer_certificate()
                cert_subject = (
                    peer_cert.get_subject().CN if peer_cert else None
                )
                cert_issuer = peer_cert.get_issuer().CN if peer_cert else None
            except Exception:  # noqa: BLE001
                cipher_name = protocol = cert_subject = cert_issuer = None
                logger.debug(
                    FIPS_TLS_HANDSHAKE,
                    peer=peer,
                    error="failed to read handshake attributes",
                )
                return
            logger.info(
                FIPS_TLS_HANDSHAKE,
                peer=peer,
                cipher_suite=cipher_name,
                protocol_version=protocol,
                cert_subject=cert_subject,
                cert_issuer=cert_issuer,
            )

    return _callback


class WebClientContextFactory(BrowserLikePolicyForHTTPS):
    def __init__(self, verify=False, **kwargs):
        super().__init__(**kwargs)
        self._verify = verify

    def creatorForNetloc(self, hostname, port):
        host_str = (
            hostname.decode("ascii")
            if isinstance(hostname, bytes)
            else hostname
        )
        if self._verify:
            opts = ClientTLSOptions(
                host_str,
                OpenSSLCertificateOptions(
                    trustRoot=platformTrust()
                ).getContext(),
            )
        else:
            opts = ClientTLSOptions(
                host_str,
                OpenSSLCertificateOptions(verify=self._verify).getContext(),
            )
        if is_fips_enabled():
            opts._ctx.set_info_callback(
                _make_fips_tls_info_callback(f"{host_str}:{port}")
            )
        else:
            # This forces Twisted to not validate the hostname of the certificate.
            opts._ctx.set_info_callback(lambda *args: None)
        return opts


def connect_ssh(
    driver_name: str,
    address: str,
    username: str,
    password: str,
) -> SSHClient:
    """Create and connect a paramiko SSHClient with FIPS-aware settings.

    In FIPS mode this uses ``RejectPolicy`` for host keys and passes explicit
    allow-lists for ciphers, kex, MACs, and key types. On success a structured FIPS_SSH_AUTH log entry
    is emitted with the negotiated cipher, MAC, and key type.

    On failure ``FIPS_CRYPTO_ERROR`` is logged (in FIPS mode) and the
    original exception is re-raised.
    """
    fips = is_fips_enabled()
    ssh_client = SSHClient()
    if fips:
        ssh_client.set_missing_host_key_policy(RejectPolicy())
    else:
        ssh_client.set_missing_host_key_policy(AutoAddPolicy())
    try:
        if fips:
            ssh_client.connect(
                hostname=address,
                username=username,
                password=password,
                **get_fips_ssh_config(),  # pyright: ignore[reportArgumentType]
            )
        else:
            ssh_client.connect(
                hostname=address,
                username=username,
                password=password,
            )
    except (SSHException, EOFError) as e:
        if fips:
            logger.error(
                FIPS_CRYPTO_ERROR,
                driver=driver_name,
                operation="ssh_connection",
                peer=address,
                error=str(e),
            )
        raise
    if fips:
        transport = ssh_client.get_transport()
        if transport is not None:
            host_key = transport.get_remote_server_key()
            logger.info(
                FIPS_SSH_AUTH,
                driver=driver_name,
                peer=address,
                result="success",
                key_type=(host_key.get_name() if host_key else None),
                cipher=getattr(transport, "local_cipher", None),
                remote_cipher=getattr(transport, "remote_cipher", None),
                mac=getattr(transport, "local_mac", None),
                remote_mac=getattr(transport, "remote_mac", None),
            )
    return ssh_client
