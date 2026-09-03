#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
"""FIPS TLS handshake auditing for aiohttp clients."""

from aiohttp import TraceConfig

from maascommon.logging.security import log_fips_tls_handshake_from_sslobj


def fips_tls_trace_config() -> TraceConfig:
    """Return an aiohttp ``TraceConfig`` that emits a ``fips_tls_handshake``
    audit event once a request has completed its TLS handshake.

    Attach it to a ``ClientSession`` via ``trace_configs=[...]``. It is a
    no-op on non-FIPS hosts and for plain-HTTP requests.
    """

    async def _on_request_end(session, trace_config_ctx, params) -> None:
        connection = getattr(params.response, "connection", None)
        transport = getattr(connection, "transport", None)
        ssl_object = (
            transport.get_extra_info("ssl_object") if transport else None
        )
        host = params.url.host
        peer = f"{host}:{params.url.port}" if host else "unknown"
        log_fips_tls_handshake_from_sslobj(ssl_object, peer=peer)

    trace_config = TraceConfig()
    trace_config.on_request_end.append(_on_request_end)
    return trace_config
