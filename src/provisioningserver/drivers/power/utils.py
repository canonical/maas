# Copyright 2019-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helpers for MAAS power drivers."""

from twisted.internet._sslverify import (
    ClientTLSOptions,
    OpenSSLCertificateOptions,
)
from twisted.internet.ssl import platformTrust
from twisted.web.client import BrowserLikePolicyForHTTPS

# OpenSSL SSL_CB_HANDSHAKE_DONE bitmask value (not exported by pyOpenSSL).
_SSL_CB_HANDSHAKE_DONE = 0x20


def _make_tls_info_callback(hostname: str, verify: bool):
    """Return an OpenSSL info callback for the given connection parameters.

    On non-FIPS hosts returns a no-op (preserving the existing behaviour of
    suppressing Twisted's hostname verification).  On FIPS hosts returns a
    callback that emits a ``fips_tls_handshake`` audit event once the TLS
    handshake completes, using the *actual* negotiated cipher and protocol
    version from the OpenSSL connection object.
    """
    from maascommon.fips import is_fips_enabled

    if not is_fips_enabled():
        return lambda *args: None

    from maascommon.logging.security import log_fips_tls_handshake

    def _cb(connection, where, _return_code):
        if not (where & _SSL_CB_HANDSHAKE_DONE):
            return
        cipher = connection.get_cipher_name() or "unknown"
        version = connection.get_protocol_version_name() or "unknown"
        peer_cert = connection.get_peer_certificate()
        if peer_cert is not None:
            issuer = peer_cert.get_issuer()
            cert_issuer = issuer.CN or str(issuer) or "unknown"
        else:
            cert_issuer = "unknown"
        log_fips_tls_handshake(
            cipher_suite=cipher,
            protocol_version=version,
            peer=hostname,
            cert_issuer=cert_issuer,
            cert_valid=verify,
        )

    return _cb


class WebClientContextFactory(BrowserLikePolicyForHTTPS):
    def __init__(self, verify=False, **kwargs):
        super().__init__(**kwargs)
        self._verify = verify

    def creatorForNetloc(self, hostname, port):
        host = hostname.decode("ascii")
        if self._verify:
            opts = ClientTLSOptions(
                host,
                OpenSSLCertificateOptions(
                    trustRoot=platformTrust()
                ).getContext(),
            )
        else:
            opts = ClientTLSOptions(
                host,
                OpenSSLCertificateOptions(verify=self._verify).getContext(),
            )
        # Install the FIPS-aware info callback; behaviour is described in
        # ``_make_tls_info_callback``.
        opts._ctx.set_info_callback(
            _make_tls_info_callback(host, self._verify)
        )
        return opts


def install_fips_tls_audit_logging(hmc_session, hostname: str) -> None:
    """Emit a ``fips_tls_handshake`` audit event for every HTTPS connection
    a zhmcclient :class:`~zhmcclient.Session` makes to ``hostname``.

    Mirrors the audit logging already installed for Twisted-Agent-based
    drivers (:class:`WebClientContextFactory` above) and for outbound
    aiohttp/stdlib-``ssl`` connections elsewhere in MAAS
    (``maasservicelayer.logging.tls``,
    ``maastemporalworker.workflow.bootresource``). ``requests``-based
    drivers (zhmcclient, used by ``hmcz.py``) have no equivalent
    first-class hook.

    ``hmc_session.session`` (the underlying ``requests.Session``) does
    not exist yet at construction time -- zhmcclient creates it lazily,
    on first logon, via its private ``_new_session()`` static method.
    This wraps that method so every ``requests.Session`` it ever
    creates (initial logon and any later re-logon) gets a custom HTTPS
    connection pool mounted that logs the negotiated cipher/protocol
    right after each TLS handshake, preserving the retry configuration
    zhmcclient itself installs.

    No-op outside FIPS mode, and a no-op (rather than raising) if a
    future zhmcclient version removes ``_new_session`` -- this is
    audit logging, not a security control, so it must never break a
    power action.
    """
    from maascommon.fips import is_fips_enabled

    if not is_fips_enabled():
        return
    original_new_session = getattr(hmc_session, "_new_session", None)
    if original_new_session is None:
        return

    from requests.adapters import DEFAULT_RETRIES, HTTPAdapter
    from urllib3.connection import HTTPSConnection
    from urllib3.connectionpool import HTTPSConnectionPool

    from maascommon.logging.security import log_fips_tls_handshake_from_sslobj

    class _FIPSAuditHTTPSConnection(HTTPSConnection):
        def connect(self):
            super().connect()
            log_fips_tls_handshake_from_sslobj(
                self.sock, peer=f"{hostname}:{self.port}"
            )

    class _FIPSAuditHTTPSConnectionPool(HTTPSConnectionPool):
        ConnectionCls = _FIPSAuditHTTPSConnection

    class _FIPSAuditHTTPAdapter(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            super().init_poolmanager(*args, **kwargs)
            self.poolmanager.pool_classes_by_scheme["https"] = (
                _FIPSAuditHTTPSConnectionPool
            )

    def _new_session_with_audit_logging(*args, **kwargs):
        requests_session = original_new_session(*args, **kwargs)
        existing_adapter = requests_session.adapters.get("https://")
        max_retries = getattr(existing_adapter, "max_retries", DEFAULT_RETRIES)
        requests_session.mount(
            "https://", _FIPSAuditHTTPAdapter(max_retries=max_retries)
        )
        return requests_session

    hmc_session._new_session = _new_session_with_audit_logging
