#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Discover MAAS CLI commands by constructing argparse tree from source."""

from importlib.abc import Loader
from importlib.machinery import ModuleSpec
import os
import sys
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock

try:
    import importlib.metadata as _ilm
except ImportError:
    _ilm = None


def add_repo_src_to_path():
    """Add repository src directory to Python path."""
    repo_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..")
    )
    src_dir = os.path.join(repo_root, "src")
    if os.path.isdir(src_dir) and src_dir not in sys.path:
        sys.path.insert(0, src_dir)


def _patch_recursively(root_mock: MagicMock, module_name: str):
    # The trickery that follows is intended to prevent two things:
    # 1 - A bunch of assignments to sys.modules
    # 2 - Maintenance here in case we simply import a different submodule
    #     of the patched module.
    class PatchedFinder:
        def find_spec(self, fullname, path, target=None):
            if fullname == module_name or fullname.startswith(
                f"{module_name}."
            ):
                return ModuleSpec(fullname, PatchedLoader())
            return None

    class PatchedLoader(Loader):
        def create_module(self, spec):
            module = ModuleType(spec.name)

            parts = spec.name.split(".")[1:]
            mock_obj = root_mock
            for part in parts:
                mock_obj = getattr(mock_obj, part)

            module.__path__ = []  # Triggers Python to treat it as a package
            module.__getattr__ = lambda name: getattr(mock_obj, name)

            return module

        def exec_module(self, module):
            pass

    sys.meta_path.insert(0, PatchedFinder())


def _patch_maas_metadata():
    """Patch importlib.metadata.distribution for 'maas' so imports succeed in-repo."""
    if _ilm is not None:
        _orig = getattr(_ilm, "distribution", None)
        if _orig is not None:

            def _fake(name):
                if name == "maas":

                    class _Dummy:
                        version = "0.0.0"

                    return _Dummy()
                return _orig(name)

            _ilm.distribution = _fake


def _patch_distro_info():
    """Patch distro_info module so imports succeed without the package installed."""
    distro_info = MagicMock()

    class FakeDistroInfo:
        def __init__(self, *args, **kwargs):
            pass

        def supported(self, *args, **kwargs):
            return []

        def all(self, *args, **kwargs):
            return []

    distro_info.UbuntuDistroInfo = FakeDistroInfo
    distro_info.DebianDistroInfo = FakeDistroInfo

    sys.modules["distro_info"] = distro_info


def _patch_seamicroclient():
    """Patch seamicroclient module so imports succeed without the package installed."""
    seamicroclient = MagicMock()
    seamicroclient.exceptions = MagicMock()
    seamicroclient.v2 = MagicMock()
    seamicroclient.v2.client = MagicMock()

    sys.modules["seamicroclient"] = seamicroclient
    sys.modules["seamicroclient.v2"] = seamicroclient.v2
    sys.modules["seamicroclient.v2.client"] = seamicroclient.v2.client


def _patch_curtin():
    """Patch curtin module so imports succeed without the package installed."""
    curtin = MagicMock()
    curtin.config = MagicMock()
    curtin.config.merge_config = MagicMock()
    curtin.pack = MagicMock()
    curtin.pack.pack_install = MagicMock()

    sys.modules["curtin"] = curtin
    sys.modules["curtin.config"] = curtin.config
    sys.modules["curtin.pack"] = curtin.pack


def _patch_tftp():
    """Patch tftp module so imports succeed without the package installed."""
    tftp = MagicMock()
    tftp.backend = MagicMock()
    tftp.backend.IReader = MagicMock()

    sys.modules["tftp"] = tftp
    sys.modules["tftp.backend"] = tftp.backend


def _patch_simplestreams():
    """Patch simplestreams module so imports succeed without the package installed."""
    simplestreams = MagicMock()
    simplestreams.util = MagicMock()
    simplestreams.mirrors = MagicMock()
    simplestreams.log = MagicMock()
    simplestreams.objectstores = MagicMock()

    sys.modules["simplestreams"] = simplestreams
    sys.modules["simplestreams.util"] = simplestreams.util
    sys.modules["simplestreams.mirrors"] = simplestreams.mirrors
    sys.modules["simplestreams.log"] = simplestreams.log
    sys.modules["simplestreams.objectstores"] = simplestreams.objectstores

def _patch_authlib():
    """Patch authlib so imports succeed."""
    authlib = MagicMock()
    _patch_recursively(authlib, "authlib")


def _patch_cryptography():
    """Patch cryptography so imports succeed."""
    cryptography = MagicMock()
    _patch_recursively(cryptography, "cryptography")


def _patch_joserfc():
    """Patch cryptography so imports succeed."""
    joserfc = MagicMock()
    _patch_recursively(joserfc, "joserfc")


def _patch_pylxd():
    """Patch cryptography so imports succeed."""
    pylxd = MagicMock()
    pylxd.client = MagicMock()
    pylxd.exceptions = MagicMock()
    sys.modules["pylxd"] = pylxd
    sys.modules["pylxd.client"] = pylxd.client
    sys.modules["pylxd.exceptions"] = pylxd.exceptions


def _patch_openssl():
    """Patch OpenSSL so imports succeed.

    In this case, we do not avoid openssl altogether. Rather,
    only some paths that interact with cryptography through twisted.
    """
    openssl = MagicMock()
    openssl._util = MagicMock()
    openssl.SSL = MagicMock()
    sys.modules["OpenSSL"] = openssl
    sys.modules["OpenSSL.SSL"] = openssl.SSL
    sys.modules["OpenSSL._util"] = openssl._util


def _patch_temporalio():
    """Patch temporalio module so imports succeed without the package installed."""

    class MockClientInterceptor:
        pass

    class MockWorkerInterceptor:
        pass

    temporalio_root_mock = MagicMock()
    temporalio_root_mock.client.ClientInterceptor = MockClientInterceptor
    temporalio_root_mock.worker.WorkerInterceptor = MockWorkerInterceptor

    sys.modules["maascommon.workflows.interceptors"] = MagicMock()

    _patch_recursively(temporalio_root_mock, "temporalio")


def _patch_paramiko():
    """Patch paramiko module so imports succeed without the package installed."""
    paramiko = MagicMock()

    sys.modules["paramiko"] = paramiko


def generate_api_description_from_source():
    if "DJANGO_SETTINGS_MODULE" not in os.environ:
        os.environ.setdefault(
            "DJANGO_SETTINGS_MODULE", "maasserver.djangosettings.settings"
        )
    import django

    django.setup()
    from maasserver.api.doc_oapi import get_api_endpoint

    return get_api_endpoint()


def get_openapi_spec() -> dict[str, str | Any]:
    """Generate and return the OpenAPI specification from MAAS source.

    This function sets up the environment, applies necessary patches,
    and generates the OpenAPI spec by introspecting the MAAS codebase.

    Returns:
        OpenAPI specification as a YAML string.
    """
    add_repo_src_to_path()
    _patch_maas_metadata()
    _patch_distro_info()
    _patch_seamicroclient()
    _patch_curtin()
    _patch_temporalio()
    _patch_tftp()
    _patch_simplestreams()
    _patch_paramiko()
    _patch_authlib()
    _patch_openssl()
    _patch_cryptography()
    _patch_joserfc()
    _patch_pylxd()
    return generate_api_description_from_source()


def main():
    """CLI entry point - print the OpenAPI spec to stdout."""
    print(get_openapi_spec())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
