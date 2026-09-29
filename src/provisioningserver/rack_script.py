# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import os
import pwd

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


def set_umask():
    # Prevent creation of world-readable (or writable, executable) files.
    os.umask(0o007)


def run():
    is_devenv = is_dev_environment()

    if not is_devenv:
        os.environ.update(
            {
                "MAAS_PATH": os.environ["SNAP"],
                "MAAS_ROOT": os.environ["SNAP_DATA"],
                "MAAS_DATA": os.path.join(os.environ["SNAP_COMMON"], "maas"),
                "MAAS_CACHE": os.path.join(
                    os.environ["SNAP_COMMON"], "maas", "cache"
                ),
                "MAAS_CLUSTER_CONFIG": os.path.join(
                    os.environ["SNAP_DATA"], "rackd.conf"
                ),
            }
        )

        # Only set the umask when running as root.
        if check_users(["root"]) == "root":
            set_umask()

    # read the shared secret and make it globally available
    shared_secret = MAAS_SHARED_SECRET.get()
    if shared_secret:
        MAAS_SECRET.set(to_bin(shared_secret))

    # Run the script.
    # Run the main provisioning script.
    from provisioningserver.__main__ import main

    main()
