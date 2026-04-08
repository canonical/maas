#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Discover MAAS CLI commands by constructing argparse tree from source."""

import os
import sys

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
    import sys
    from unittest.mock import MagicMock

    # Create a fake distro_info module
    distro_info = MagicMock()

    # Create minimal fake classes for common distroinfo types
    class FakeDistroInfo:
        def __init__(self, *args, **kwargs):
            pass

        def supported(self, *args, **kwargs):
            return []

        def all(self, *args, **kwargs):
            return []

    distro_info.UbuntuDistroInfo = FakeDistroInfo
    distro_info.DebianDistroInfo = FakeDistroInfo

    # Inject the fake module into sys.modules
    sys.modules["distro_info"] = distro_info


def _patch_seamicroclient():
    """Patch seamicroclient module so imports succeed without the package installed."""
    import sys
    from unittest.mock import MagicMock

    # Create a fake seamicroclient module with v2.client
    seamicroclient = MagicMock()
    seamicroclient.exceptions = MagicMock()
    seamicroclient.v2 = MagicMock()
    seamicroclient.v2.client = MagicMock()

    # Inject the fake modules into sys.modules
    sys.modules["seamicroclient"] = seamicroclient
    sys.modules["seamicroclient.v2"] = seamicroclient.v2
    sys.modules["seamicroclient.v2.client"] = seamicroclient.v2.client


def _patch_curtin():
    """Patch curtin module so imports succeed without the package installed."""
    import sys
    from unittest.mock import MagicMock

    # Create a fake curtin module with config and pack submodules
    curtin = MagicMock()
    curtin.config = MagicMock()
    curtin.config.merge_config = MagicMock()
    curtin.pack = MagicMock()
    curtin.pack.pack_install = MagicMock()

    # Inject the fake modules into sys.modules
    sys.modules["curtin"] = curtin
    sys.modules["curtin.config"] = curtin.config
    sys.modules["curtin.pack"] = curtin.pack


def _patch_tftp():
    """Patch tftp module so imports succeed without the package installed."""
    import sys
    from unittest.mock import MagicMock

    # Create a fake tftp module with backend submodule
    tftp = MagicMock()
    tftp.backend = MagicMock()
    tftp.backend.IReader = MagicMock()

    # Inject the fake modules into sys.modules
    sys.modules["tftp"] = tftp
    sys.modules["tftp.backend"] = tftp.backend


def generate_api_description_from_source():
    if "DJANGO_SETTINGS_MODULE" not in os.environ:
        os.environ.setdefault(
            "DJANGO_SETTINGS_MODULE", "maasserver.djangosettings.settings"
        )
    import django

    django.setup()
    from maasserver.api.doc_oapi import get_api_endpoint

    return get_api_endpoint()


def get_openapi_spec() -> str:
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
    _patch_tftp()
    return generate_api_description_from_source()


def main():
    """CLI entry point - print the OpenAPI spec to stdout."""
    print(get_openapi_spec())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
