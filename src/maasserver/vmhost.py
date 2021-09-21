from urllib.parse import urlparse

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks

from maasserver.clusterrpc.pods import (
    discover_pod,
    get_best_discovered_result,
    send_pod_commissioning_results,
)
from maasserver.exceptions import PodProblem
from maasserver.models import (
    BMCRoutableRackControllerRelationship,
    Event,
    RackController,
)
from maasserver.rpc import getClientFromIdentifiers
from maasserver.utils import absolute_reverse
from maasserver.utils.orm import post_commit_do, transactional
from maasserver.utils.threads import deferToDatabase
from metadataserver.models import NodeKey
from provisioningserver.events import EVENT_TYPES


@inlineCallbacks
def request_commissioning_results(pod):
    """Request commissioning results from machines associated with the Pod."""
    nodes = yield deferToDatabase(lambda: list(pod.hints.nodes.all()))
    # libvirt Pods don't create machines for the host.
    if not nodes:
        return pod
    client_identifiers = yield deferToDatabase(pod.get_client_identifiers)
    client = yield getClientFromIdentifiers(client_identifiers)
    for node in nodes:
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
                urlparse(
                    absolute_reverse("metadata-version", args=["latest"])
                ),
            )
        except PodProblem as e:
            yield deferToDatabase(
                Event.objects.create_node_event,
                node,
                EVENT_TYPES.NODE_COMMISSIONING_EVENT_FAILED,
                event_description=str(e),
            )
    return pod


def discover_and_sync_vmhost(vmhost, user):
    """Sync resources and information for the VM host from discovery."""
    try:
        discovered = discover_pod(
            vmhost.power_type,
            vmhost.power_parameters,
            pod_id=vmhost.id,
            name=vmhost.name,
        )
        discovered_pod = get_best_discovered_result(discovered)
    except Exception as error:
        raise PodProblem(str(error))

    if discovered_pod is None:
        raise PodProblem(
            "Unable to start the VM host discovery process. "
            "No rack controllers connected."
        )
    _update_db(discovered_pod, discovered, vmhost, user)
    # The data isn't committed to the database until the transaction is
    # complete. The commissioning results must be sent after the
    # transaction completes so the metadata server can process the
    # data.
    post_commit_do(
        reactor.callLater,
        0,
        request_commissioning_results,
        vmhost,
    )
    return vmhost


async def discover_and_sync_vmhost_async(vmhost, user):
    """Sync resources and information for the VM host from discovery."""
    try:
        discovered = await discover_pod(
            vmhost.power_type,
            vmhost.power_parameters,
            pod_id=vmhost.id,
            name=vmhost.name,
        )
        discovered_pod = get_best_discovered_result(discovered)
    except Exception as error:
        raise PodProblem(str(error))

    if discovered_pod is None:
        raise PodProblem(
            "Unable to start the VM host discovery process. "
            "No rack controllers connected."
        )

    await deferToDatabase(
        transactional(_update_db), discovered_pod, discovered, vmhost, user
    )
    await request_commissioning_results(vmhost)
    return vmhost


def _update_db(discovered_pod, discovered, vmhost, user):
    # If this is a new instance it will be stored in the database at the end of
    # sync.
    vmhost.sync(discovered_pod, user)

    # Save which rack controllers can route and which cannot.
    discovered_rack_ids = [rack_id for rack_id, _ in discovered[0].items()]
    for rack_controller in RackController.objects.all():
        routable = rack_controller.system_id in discovered_rack_ids
        (
            relation,
            created,
        ) = BMCRoutableRackControllerRelationship.objects.get_or_create(
            bmc=vmhost.as_bmc(),
            rack_controller=rack_controller,
            defaults={"routable": routable},
        )
        if not created and relation.routable != routable:
            relation.routable = routable
            relation.save()
    return vmhost
