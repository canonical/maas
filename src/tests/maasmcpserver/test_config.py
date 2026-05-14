# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import importlib


def _load_config_class():
    module = importlib.import_module("maasmcpserver.config")
    return importlib.reload(module).MaasServerConfig


def test_defaults_without_maas_url(monkeypatch):
    monkeypatch.delenv("MAAS_URL", raising=False)
    monkeypatch.delenv("maas_url", raising=False)

    config = _load_config_class()()

    assert config.maas_url == "http://localhost:5240"


def test_defaults(monkeypatch):
    monkeypatch.setenv("MAAS_URL", "http://maas.example.com/")

    config = _load_config_class()()

    assert config.maas_url == "http://maas.example.com/"
    assert config.mcp_socket_path
    assert config.maas_request_timeout == 30
    assert config.maas_tls_verify is True
    assert config.log_level == "INFO"


def test_no_forbidden_fields(monkeypatch):
    monkeypatch.setenv("MAAS_URL", "http://maas.example.com/")

    config = _load_config_class()()

    for attr in (
        "mcp_host",
        "mcp_port",
        "tls_cert",
        "tls_key",
        "maas_api_key",
    ):
        assert not hasattr(config, attr)
