# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The MAAS Provisioning Server, now referred to as Cluster."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


from twisted.application.service import MultiService
from twisted.internet.protocol import Factory

CLUSTERD_DB_PATH = '/var/lib/maas/clusterd.db'
CLUSTERD_DB_maas_url = 'MAAS_URL'
CLUSTERD_DB_generator = 'generator'
CLUSTERD_DB_cluster_uuid = 'CLUSTER_UUID'

# The cluster's services. This is initialised by
# ProvisioningServiceMaker.
services = MultiService()

# Make t.i.protocol.Factory quiet. Its jabbering is mind-numbingly
# useless.
Factory.noisy = False


try:
    import maasfascist
    maasfascist  # Silence lint.
except ImportError:
    pass
