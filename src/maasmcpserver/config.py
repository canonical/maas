# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic_settings import BaseSettings, SettingsConfigDict

from maascommon.path import get_maas_data_path


class MaasServerConfig(BaseSettings):
    """MAAS MCP Server configuration."""

    # Required fields (default matches the MAAS region API port on the same host)
    maas_url: str = "http://localhost:5240"

    # Optional fields with defaults
    mcp_socket_path: str = get_maas_data_path("mcp.sock")
    maas_request_timeout: int = 30
    maas_tls_verify: bool = True
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=None,
        case_sensitive=False,
    )
