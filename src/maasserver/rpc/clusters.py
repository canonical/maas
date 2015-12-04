# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to clusters (a.k.a. node groups)."""

__all__ = [
    "register_cluster",
]

import json

from django.core.exceptions import ValidationError
from maasserver.enum import NODEGROUP_STATUS
from maasserver.forms import NodeGroupDefineForm
from maasserver.models.nodegroup import NodeGroup
from maasserver.utils.orm import transactional
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.twisted import synchronous


maaslog = get_maas_logger('rpc.clusters')


@synchronous
@transactional
def register_cluster(
        uuid, name=None, domain=None, networks=None, url=None,
        ip_addr_json=None):
    """Register a new cluster, if not already registered.

    If the master has not been configured yet, this nodegroup becomes the
    master. In that situation, if the uuid is also the one configured locally
    (meaning that the cluster controller is running on the same host as this
    region controller), the new master is also automatically accepted.

    Note that this function should only ever be called once the cluster has
    been authenticated, by a shared-secret for example. The reason is that the
    cluster will be created in an accepted state.

    """
    try:
        cluster = NodeGroup.objects.get_by_natural_key(uuid)
    except NodeGroup.DoesNotExist:
        master = NodeGroup.objects.ensure_master()
        if master.uuid in ('master', ''):
            # The master cluster is not yet configured. No actual cluster
            # controllers have registered yet. All we have is the default
            # placeholder. We let the cluster controller that's making this
            # request take the master's place.
            cluster = master
            message = "New cluster registered as master"
        else:
            cluster = None
            message = "New cluster registered"
    else:
        message = "Cluster registered"

    # Massage the data so that we can pass it into NodeGroupDefineForm.
    data = {"uuid": uuid}
    if name is not None:
        data["cluster_name"] = name
    if domain is not None:
        data["name"] = domain

    # Populate networks when there are no preexisting networks.
    if networks is not None or ip_addr_json is not None:
        if cluster is None or not cluster.nodegroupinterface_set.exists():
            if ip_addr_json is not None:
                data["ip_addr_json"] = ip_addr_json
            if networks is not None:
                # Convert this data structure to a string so that it works
                # inside the Django form.
                data["interfaces"] = json.dumps(networks)

    form = NodeGroupDefineForm(
        data=data, status=NODEGROUP_STATUS.ENABLED,
        instance=cluster)

    if form.is_valid():
        cluster = form.save()
        maaslog.info("%s: %s (%s)" % (
            message, cluster.cluster_name, cluster.uuid))
    else:
        raise ValidationError(form.errors)

    # Update `cluster.maas_url` from the given URL, but only when the hostname
    # is not 'localhost' (i.e. the default value used when the master cluster
    # connects).
    if url is not None and url.hostname != "localhost":
        cluster.maas_url = url.geturl()
        cluster.save()

    return cluster
