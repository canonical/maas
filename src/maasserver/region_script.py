# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import grp
import os

from provisioningserver.config import is_dev_environment


def check_user():
    # At present, only root should execute this.
    if os.getuid() != 0:
        raise SystemExit("This utility may only be run as root.")


def set_group():
    # Ensure that we're running as the `maas` group.
    try:
        gr_maas = grp.getgrnam("maas")
    except KeyError:
        raise SystemExit("No such group: maas")
    else:
        os.setegid(gr_maas.gr_gid)


def set_umask():
    # Prevent creation of world-readable (or writable, executable) files.
    os.umask(0o007)


def run_django(is_snap, is_devenv):
    # Force the production MAAS Django configuration.
    if is_snap:
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
                "MAAS_IMAGES_KEYRING_FILEPATH": (
                    "/snap/maas/current/usr/share/keyrings/"
                    "ubuntu-cloudimage-keyring.gpg"
                ),
                "MAAS_THIRD_PARTY_DRIVER_SETTINGS": os.path.join(
                    os.environ["SNAP"], "etc/maas/drivers.yaml"
                ),
            }
        )
    elif is_devenv:
        os.environ.update(
            {
                "DJANGO_SETTINGS_MODULE": "maasserver.djangosettings.development",
                "MAAS_THIRD_PARTY_DRIVER_SETTINGS": "package-files/etc/maas/drivers.yaml",
            }
        )
    else:
        os.environ[
            "DJANGO_SETTINGS_MODULE"
        ] = "maasserver.djangosettings.settings"

    # Let Django do the rest.
    from django.core import management

    management.execute_from_command_line()


def run():
    is_snap = "SNAP" in os.environ
    is_devenv = is_dev_environment()
    if not is_devenv:
        check_user()
        if not is_snap:
            set_group()
        set_umask()
    run_django(is_snap, is_devenv)
