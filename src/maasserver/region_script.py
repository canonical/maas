# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import grp
import os


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


def run_django():
    # Force the production MAAS Django configuration.
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE", "maasserver.djangosettings.settings")

    # Let Django do the rest.
    from django.core import management
    management.execute_from_command_line()


def run():
    check_user()
    set_group()
    set_umask()
    run_django()
