# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Rack controller config management module."""

from dataclasses import asdict, dataclass
import os

import yaml

from provisioningserver.utils.fs import atomic_write
from provisioningserver.utils.twisted import synchronous


def get_rack_controller_config_path():
    """Location of rack controller configuration files."""
    return os.getenv(
        "MAAS_RACK_CONTROLLER_CONFIG", "/etc/maas/rackcontroller.yaml"
    )


@dataclass(frozen=True)
class RackControllerHTTPProxyCacheConfig:
    dir: str
    size: int


@dataclass(frozen=True)
class RackControllerHTTPProxyConfig:
    cache: RackControllerHTTPProxyCacheConfig


@dataclass(frozen=True)
class RackControllerTemporalConfig:
    host: str
    port: int
    encryption_key: str


@dataclass(frozen=True)
class RackControllerLogConfig:
    level: str


@dataclass(frozen=True)
class RackControllerMetricsConfig:
    enabled: bool


@dataclass(frozen=True)
class RackControllerServicesConfig:
    http_proxy: RackControllerHTTPProxyConfig


@dataclass(frozen=True)
class RackControllerObservabilityConfig:
    logging: RackControllerLogConfig
    metrics: RackControllerMetricsConfig


@dataclass(frozen=True)
class RackControllerTLSConfig:
    key_file: str
    cert_file: str
    ca_file: str


@dataclass(frozen=True)
class RackControllerConfig:
    maas_uuid: str
    system_id: str
    controller: str
    temporal: RackControllerTemporalConfig
    services: RackControllerServicesConfig
    observability: RackControllerObservabilityConfig
    tls: RackControllerTLSConfig


@synchronous
def write_config(config: RackControllerConfig):
    """Write rack controller configuration."""

    header = b"# WARNING: MAAS will overwrite any changes made here.\n\n"
    dump = yaml.safe_dump(asdict(config), encoding="utf-8")
    data = header + dump
    atomic_write(data, get_rack_controller_config_path())
