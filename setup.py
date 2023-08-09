# Copyright 2012-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Setuptools installer for MAAS."""

from os.path import dirname, join

from setuptools import find_packages, setup


def read(filename):
    """Return the whitespace-stripped content of `filename`."""
    path = join(dirname(__file__), filename)
    with open(path, "r") as fin:
        return fin.read().strip()


setup(
    name="maas",
    version="2.9.3rc3",
    url="https://maas.io/",
    license="AGPLv3",
    description="Metal As A Service",
    long_description=read("README.rst"),
    author="MAAS Developers",
    author_email="maas-devel@lists.launchpad.net",
    packages=find_packages(
        where="src",
        exclude=["*.testing", "*.tests", "maastesting", "maastesting.*"],
    ),
    package_dir={"": "src"},
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "maas = maascli:main",
            "maas-common = provisioningserver.rack_script:run",
            "maas-rack = provisioningserver.rack_script:run",
            "maas-power = provisioningserver.power_driver_command:run",
            "maas-region = maasserver.region_script:run",
            "rackd = provisioningserver.server:run",
            "regiond = maasserver.server:run",
            # Test scrips
            "test.region = maastesting.scripts:run_region",
            "test.region.legacy = maastesting.scripts:run_region_legacy",
            "test.rack = maastesting.scripts:run_rack",
            "test.cli = maastesting.scripts:run_cli",
            "test.testing = maastesting.scripts:run_testing",
            "test.parallel = maastesting.scripts:run_parallel",
        ]
    },
    data_files=[
        ("/etc/maas", ["etc/maas/drivers.yaml"]),
        ("/usr/share/maas", ["contrib/maas-http.conf"]),
        (
            "/etc/maas/preseeds",
            [
                "contrib/preseeds_v2/commissioning",
                "contrib/preseeds_v2/enlist",
                "contrib/preseeds_v2/curtin",
                "contrib/preseeds_v2/curtin_userdata",
                "contrib/preseeds_v2/curtin_userdata_centos",
                "contrib/preseeds_v2/curtin_userdata_custom",
                "contrib/preseeds_v2/curtin_userdata_suse",
                "contrib/preseeds_v2/curtin_userdata_windows",
            ],
        ),
        (
            "/usr/bin",
            ["scripts/maas-generate-winrm-cert", "scripts/uec2roottar"],
        ),
        ("/usr/sbin", ["scripts/maas-dhcp-helper"]),
        (
            "/usr/lib/maas",
            [
                "scripts/dhcp-monitor",
                "scripts/beacon-monitor",
                "scripts/network-monitor",
                "scripts/maas-delete-file",
                "scripts/maas-test-enlistment",
                "scripts/maas-write-file",
                "scripts/unverified-ssh",
            ],
        ),
    ],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Information Technology",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: JavaScript",
        "Programming Language :: Python :: 3",
        "Topic :: System :: Systems Administration",
    ],
)
