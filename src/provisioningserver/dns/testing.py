# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test helpers for DNS."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "patch_dns_config_path",
    "patch_dns_default_controls",
    "patch_dns_rndc_port",
]

import sys

from fixtures import EnvironmentVariable


def patch_dns_config_path(testcase, config_dir=None):
    """Set the DNS config dir to a temporary directory, and return its path."""
    fsenc = sys.getfilesystemencoding()
    if config_dir is None:
        config_dir = testcase.make_dir()
    if isinstance(config_dir, unicode):
        config_dir = config_dir.encode(fsenc)
    testcase.useFixture(
        EnvironmentVariable(b"MAAS_DNS_CONFIG_DIR", config_dir))
    testcase.useFixture(
        EnvironmentVariable(b"MAAS_BIND_CONFIG_DIR", config_dir))
    return config_dir.decode(fsenc)


def patch_dns_rndc_port(testcase, port):
    testcase.useFixture(
        EnvironmentVariable(b"MAAS_DNS_RNDC_PORT", b"%d" % port))


def patch_dns_default_controls(testcase, enable):
    testcase.useFixture(
        EnvironmentVariable(
            b"MAAS_DNS_DEFAULT_CONTROLS",
            b"1" if enable else b"0"))
