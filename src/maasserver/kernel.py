# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Generate kernel command-line for inclusion in PXE configs.

This is a TRANSITIONAL module. This functionality will move to the pxeconfig()
view in the most likely scenario.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'compose_kernel_command_line',
    ]

from maasserver.preseed import (
    compose_enlistment_preseed_url,
    compose_preseed_url,
    )
from maasserver.server_address import get_maas_facing_server_address
from provisioningserver.kernel_opts import (
    compose_kernel_command_line_new,
    KernelParameters,
    )


def compose_kernel_command_line(node, arch, subarch, purpose):
    """Generate a line of kernel options for booting `node`.

    Include these options in the PXE config file's APPEND argument.

    The node may be None, in which case it will boot into enlistment.
    """
    # XXX JeroenVermeulen 2012-08-06 bug=1013146: Stop hard-coding this.
    release = 'precise'

    # TODO: This is probably not enough!
    domain = 'local.lan'

    if node is None:
        preseed_url = compose_enlistment_preseed_url()
    else:
        preseed_url = compose_preseed_url(node)

    if node is None:
        # Not a known host; still needs enlisting.  Make up a name.
        hostname = 'maas-enlist'
    else:
        hostname = node.hostname

    server_address = get_maas_facing_server_address()

    params = KernelParameters(
        arch=arch, subarch=subarch, release=release, purpose=purpose,
        hostname=hostname, domain=domain, preseed_url=preseed_url,
        log_host=server_address, fs_host=server_address)

    return compose_kernel_command_line_new(params)
