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
        # Replace Twisted's default info callback (which does hostname
        # verification) with our own.  On non-FIPS hosts this is a no-op,
        # preserving the previous behaviour.  On FIPS hosts it emits a
        # structured audit event at handshake completion.
        opts._ctx.set_info_callback(
            _make_tls_info_callback(host, self._verify)
        )
        return opts
