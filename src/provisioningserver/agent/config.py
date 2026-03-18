# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS Agent config management module."""

from dataclasses import asdict, dataclass
import os

import yaml

from provisioningserver.utils.fs import atomic_write
from provisioningserver.utils.twisted import synchronous

MAAS_AGENT_CONF_TEMPLATE = "agent.yaml.template"


def get_agent_config_path():
    """Location of MAAS Agent configuration files."""
    return os.getenv("MAAS_AGENT_CONFIG", "/etc/maas/agent.yaml")


@dataclass(frozen=True)
class AgentHTTPProxyCacheConfig:
    dir: str
    size: int


@dataclass(frozen=True)
class AgentHTTPProxyConfig:
    cache: AgentHTTPProxyCacheConfig


@dataclass(frozen=True)
class AgentTemporalConfig:
    host: str
    port: int
    encryption_key: str


@dataclass(frozen=True)
class AgentLogConfig:
    level: str


@dataclass(frozen=True)
class AgentServicesConfig:
    http_proxy: AgentHTTPProxyConfig


@dataclass(frozen=True)
class AgentObservabilityConfig:
    logging: AgentLogConfig


@dataclass(frozen=True)
class AgentTLSConfig:
    key_file: str
    cert_file: str
    ca_file: str


@dataclass(frozen=True)
class AgentConfig:
    maas_uuid: str
    system_id: str
    controller: str
    temporal: AgentTemporalConfig
    services: AgentServicesConfig
    observability: AgentObservabilityConfig
    tls: AgentTLSConfig


@synchronous
def write_config(config: AgentConfig):
    """Write MAAS Agent configuration."""

    header = b"# WARNING: MAAS will overwrite any changes made here.\n\n"
    dump = yaml.safe_dump(asdict(config), encoding="utf-8")
    data = header + dump
    atomic_write(data, get_agent_config_path())
