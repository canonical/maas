# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC relating to boot images."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "import_boot_images",
    "list_boot_images",
    "is_import_boot_images_running",
    ]


from provisioningserver.auth import get_maas_user_gpghome
from provisioningserver.boot import tftppath
from provisioningserver.config import Config
from provisioningserver.import_images import boot_resources
from provisioningserver.utils.env import environment_variables
from provisioningserver.utils.twisted import synchronous
from twisted.internet.defer import DeferredLock
from twisted.internet.threads import deferToThread

# Lock is used so more than one import is not running at the same time.
import_lock = DeferredLock()


def list_boot_images():
    """List the boot images that exist on the cluster."""
    return tftppath.list_boot_images(
        Config.load_from_cache()['tftp']['resource_root'])


@synchronous
def _run_import(sources):
    """Run the import.

    This is function is synchronous so it must be called with deferToThread.
    """
    variables = {
        'GNUPGHOME': get_maas_user_gpghome(),
        }
    with environment_variables(variables):
        boot_resources.import_images(sources)


def import_boot_images(sources):
    """Imports the boot images from the given sources."""
    if not import_lock.locked:
        return import_lock.run(deferToThread, _run_import, sources)


def is_import_boot_images_running():
    """Return True if the import process is currently running."""
    return import_lock.locked
