# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import grp
import os
import pwd
import sys

from provisioningserver.config import is_dev_environment
from provisioningserver.security import to_bin
from provisioningserver.utils.env import MAAS_SECRET, MAAS_SHARED_SECRET


def check_users(users):
    """Check that the runnig user is in users."""
    uid = os.getuid()
    for user in users:
        if user is None:
            # Special case: this means any user is allowed.
            return None
        user_uid = pwd.getpwnam(user)[2]
        if uid == user_uid:
            return user
    raise SystemExit("This utility may only be run as %s." % ", ".join(users))


def set_group():
    # Ensure that we're running as the `maas` group.
    try:
        gr_maas = grp.getgrnam("maas")
    except KeyError:
        raise SystemExit("No such group: maas")  # noqa: B904
    else:
        os.setegid(gr_maas.gr_gid)


def set_umask():
    # Prevent creation of world-readable (or writable, executable) files.
    os.umask(0o007)


def run():
    is_snap = "SNAP" in os.environ
    is_devenv = is_dev_environment()

    if not is_devenv:
        if is_snap:
            os.environ.update(
                {
                    "MAAS_PATH": os.environ["SNAP"],
                    "MAAS_ROOT": os.environ["SNAP_DATA"],
                    "MAAS_DATA": os.path.join(
                        os.environ["SNAP_COMMON"], "maas"
                    ),
                    "MAAS_CACHE": os.path.join(
                        os.environ["SNAP_COMMON"], "maas", "cache"
                    ),
                    "MAAS_CLUSTER_CONFIG": os.path.join(
                        os.environ["SNAP_DATA"], "rackd.conf"
                    ),
                }
            )

        users = ["root"]
        # Allow dhcpd user to call dhcp-notify, and maas user to call
        # observe-arp.
        if not is_snap and len(sys.argv) > 1:
            if sys.argv[1] == "dhcp-notify":
                users.append("dhcpd")
            if sys.argv[1] == "observe-arp":
                users.append("maas")
            if sys.argv[1] == "observe-beacons":
                users.append("maas")
            if sys.argv[1] == "observe-mdns":
                # Any user can call this. (It might be necessary for a normal
                # user to call this for support/debugging purposes.)
                users.append(None)

        # Only set the group and umask when running as root.
        if check_users(users) == "root":
            if not is_snap:
                set_group()
            set_umask()

    # read the shared secret and make it globally available
    shared_secret = MAAS_SHARED_SECRET.get()
    if shared_secret:
        MAAS_SECRET.set(to_bin(shared_secret))

    # Run the script.
    # Run the main provisioning script.
    from provisioningserver.__main__ import main

    main()
