# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test helpers for DNS."""

from fixtures import EnvironmentVariable


def patch_dns_config_path(testcase, config_dir=None):
    """Set the DNS config dir to a temporary directory, and return its path."""
    if config_dir is None:
        config_dir = testcase.make_dir()
    testcase.useFixture(EnvironmentVariable("MAAS_DNS_CONFIG_DIR", config_dir))
    testcase.useFixture(
        EnvironmentVariable("MAAS_BIND_CONFIG_DIR", config_dir)
    )
    return config_dir


def patch_dns_rndc_port(testcase, port):
    testcase.useFixture(EnvironmentVariable("MAAS_DNS_RNDC_PORT", "%d" % port))


def patch_dns_default_controls(testcase, enable):
    testcase.useFixture(
        EnvironmentVariable(
            "MAAS_DNS_DEFAULT_CONTROLS", "1" if enable else "0"
        )
    )
