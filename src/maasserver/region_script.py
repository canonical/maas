# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import os

from provisioningserver.config import is_dev_environment


def check_user():
    # At present, only root should execute this.
    if os.getuid() != 0:
        raise SystemExit("This utility may only be run as root.")


def set_umask():
    # Prevent creation of world-readable (or writable, executable) files.
    os.umask(0o007)


def run_django(is_devenv):
    # Force the production MAAS Django configuration.
    if is_devenv:
        os.environ.update(
            {
                "DJANGO_SETTINGS_MODULE": "maasserver.djangosettings.development",
                "MAAS_THIRD_PARTY_DRIVER_SETTINGS": "package-files/etc/maas/drivers.yaml",
            }
        )
    else:
        snap_data = os.environ["SNAP_DATA"]
        os.environ.update(
            {
                "DJANGO_SETTINGS_MODULE": "maasserver.djangosettings.snap",
                "MAAS_PATH": os.environ["SNAP"],
                "MAAS_ROOT": snap_data,
                "MAAS_DATA": os.path.join(os.environ["SNAP_COMMON"], "maas"),
                "MAAS_REGION_CONFIG": os.path.join(snap_data, "regiond.conf"),
                "MAAS_DNS_CONFIG_DIR": os.path.join(snap_data, "bind"),
                "MAAS_PROXY_CONFIG_DIR": os.path.join(snap_data, "proxy"),
                "MAAS_SYSLOG_CONFIG_DIR": os.path.join(snap_data, "syslog"),
                "MAAS_ZONE_FILE_CONFIG_DIR": os.path.join(snap_data, "bind"),
                "MAAS_THIRD_PARTY_DRIVER_SETTINGS": os.path.join(
                    os.environ["SNAP"], "etc/maas/drivers.yaml"
                ),
            }
        )

    # Let Django do the rest.
    from django.core import management

    management.execute_from_command_line()


def run():
    is_devenv = is_dev_environment()
    if not is_devenv:
        check_user()
        set_umask()
    run_django(is_devenv)
