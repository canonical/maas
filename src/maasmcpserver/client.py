# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from time import monotonic
from typing import Any

import httpx

from maasmcpserver.config import MaasServerConfig
from maasmcpserver.errors import MAASPermissionError, MAASUnreachableError
from maasmcpserver.logging_events import log_maas_request, log_maas_response
from maasmcpserver.middleware import get_session_id


class MAASClientPool:
    """Long-lived HTTP connection pool shared across all requests.

    A single pool is created at startup and closed on shutdown, so
    connections to the MAAS API are reused across tool calls rather
    than torn down and re-established on every request.

    Use :meth:`client` to obtain a :class:`MAASClient` bound to a
    specific Bearer token for a single request.
    """

    def __init__(self, config: MaasServerConfig) -> None:
        self.config = config
        self._http = httpx.AsyncClient(verify=config.maas_tls_verify)

    def client(self, api_key: str) -> "MAASClient":
        """Return a request-scoped client that shares this pool."""
        return MAASClient(self.config, api_key, self._http)

    async def aclose(self) -> None:
        """Close the underlying connection pool."""
        await self._http.aclose()


class MAASClient:
    """Request-scoped MAAS API client.

    Holds a per-request Bearer token but shares the underlying
    :class:`httpx.AsyncClient` (and its connection pool) with the
    :class:`MAASClientPool` that created it.  Do not close this object
    directly; close the pool instead.
    """

    def __init__(
        self,
        config: MaasServerConfig,
        api_key: str,
        http: httpx.AsyncClient,
    ) -> None:
        self.config = config
        self.api_key = api_key
        self.client = http

    async def _request(
        self,
        method: str,
        url_pattern: str,
        path_params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        url = self._build_url(url_pattern, path_params)
        headers = {"Authorization": f"Bearer {self.api_key}"}
        timeout = httpx.Timeout(self.config.maas_request_timeout)
        start = monotonic()
        session_id = get_session_id()

        log_maas_request(session_id, method, url_pattern)

        try:
            response = await self.client.request(
                method=method,
                url=url,
                headers=headers,
                json=body,
                params=query_params,
                timeout=timeout,
            )
        except httpx.TimeoutException as error:
            duration_ms = self._duration_ms(start)
            log_maas_response(
                session_id,
                http_status=0,
                duration_ms=duration_ms,
                error="maas_unreachable",
            )
            raise MAASUnreachableError(url_pattern, "timeout") from error
        except httpx.ConnectError as error:
            duration_ms = self._duration_ms(start)
            log_maas_response(
                session_id,
                http_status=0,
                duration_ms=duration_ms,
                error="maas_unreachable",
            )
            raise MAASUnreachableError(
                url_pattern,
                "connection_refused",
            ) from error

        if response.status_code in {401, 403}:
            raise MAASPermissionError(response.status_code)

        duration_ms = self._duration_ms(start)
        log_maas_response(
            session_id,
            http_status=response.status_code,
            duration_ms=duration_ms,
        )
        response.raise_for_status()
        return response

    async def get(
        self,
        url_pattern: str,
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        return await self._request(
            method="GET",
            url_pattern=url_pattern,
            path_params=path_params,
            query_params=query_params,
        )

    async def post(
        self,
        url_pattern: str,
        path_params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> httpx.Response:
        return await self._request(
            method="POST",
            url_pattern=url_pattern,
            path_params=path_params,
            body=body,
        )

    async def put(
        self,
        url_pattern: str,
        path_params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> httpx.Response:
        return await self._request(
            method="PUT",
            url_pattern=url_pattern,
            path_params=path_params,
            body=body,
        )

    async def delete(
        self,
        url_pattern: str,
        path_params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        return await self._request(
            method="DELETE",
            url_pattern=url_pattern,
            path_params=path_params,
        )

    def _build_url(
        self,
        url_pattern: str,
        path_params: dict[str, Any] | None,
    ) -> str:
        resolved_path = url_pattern.format(**(path_params or {}))
        base_url = self.config.maas_url.rstrip("/")
        if resolved_path.startswith("/"):
            return f"{base_url}{resolved_path}"
        return f"{base_url}/{resolved_path}"

    def _duration_ms(self, start: float) -> int:
        return int((monotonic() - start) * 1000)
