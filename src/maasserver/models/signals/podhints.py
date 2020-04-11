# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to PodHints changes."""

__all__ = ["signals"]

from urllib.parse import urlparse

from django.db.models.signals import m2m_changed
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks

from maasserver.clusterrpc.pods import send_pod_commissioning_results
from maasserver.exceptions import PodProblem
from maasserver.models import Event, PodHints
from maasserver.rpc import getClientFromIdentifiers
from maasserver.utils import absolute_reverse
from maasserver.utils.orm import post_commit_do
from maasserver.utils.signals import SignalsManager
from maasserver.utils.threads import deferToDatabase
from metadataserver.models import NodeKey
from provisioningserver.events import EVENT_TYPES

signals = SignalsManager()


@inlineCallbacks
def request_commissioning_results(pod, node):
    client_identifiers = yield deferToDatabase(pod.get_client_identifiers)
    client = yield getClientFromIdentifiers(client_identifiers)
    token = yield deferToDatabase(NodeKey.objects.get_token_for_node, node)
    try:
        yield send_pod_commissioning_results(
            client,
            pod.id,
            pod.name,
            pod.power_type,
            node.system_id,
            pod.power_parameters,
            token.consumer.key,
            token.key,
            token.secret,
            urlparse(absolute_reverse("metadata-version", args=["latest"])),
        )
    except PodProblem as e:
        yield deferToDatabase(
            Event.objects.create_node_event,
            node,
            EVENT_TYPES.NODE_COMMISSIONING_EVENT_FAILED,
            event_description=str(e),
        )


def pod_nodes_changed(
    sender, instance, action, reverse, model, pk_set, **kwargs
):
    if action == "post_add":
        for node in instance.nodes.filter(id__in=pk_set):
            # The data isn't committed to the database until the transaction is
            # complete. The commissioning results must be sent after the
            # transaction completes so the metadata server can process the
            # data.
            post_commit_do(
                reactor.callLater,
                0,
                request_commissioning_results,
                instance.pod,
                node,
            )
    elif action == "post_remove":
        # Recalculate resources based on the remaining Nodes.
        instance.pod.sync_hints_from_nodes()


signals.watch(m2m_changed, pod_nodes_changed, sender=PodHints.nodes.through)


# Enable all signals by default
signals.enable()
