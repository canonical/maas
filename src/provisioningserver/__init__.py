# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The MAAS Provisioning Server, now referred to as Cluster."""

from twisted.application.service import MultiService

# The cluster's services. This is initialised by
# ProvisioningServiceMaker.
services = MultiService()
