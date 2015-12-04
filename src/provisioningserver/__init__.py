# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The MAAS Provisioning Server, now referred to as Cluster."""

__all__ = []


from twisted.application.service import MultiService
from twisted.internet.protocol import Factory

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
