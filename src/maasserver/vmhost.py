from urllib.parse import urlparse

from netaddr import valid_ipv6
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
    NodeKey,
    Pod,
    RackController,
    Tag,
    VMCluster,
)
from maasserver.models.bmc import create_pod
from maasserver.rpc import getClientFromIdentifiers
from maasserver.utils import absolute_reverse
from maasserver.utils.orm import post_commit_do, transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.drivers.pod import DiscoveredCluster, DiscoveredPod
from provisioningserver.events import EVENT_TYPES


def ensure_pod_console_logging_tag() -> Tag:
    tag, _ = Tag.objects.get_or_create(
        name="pod-console-logging",
        defaults={"kernel_opts": "console=tty1 console=ttyS0"},
    )
    return tag


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
        power_params = yield deferToDatabase(pod.get_power_parameters)
        url = yield deferToDatabase(
            absolute_reverse, "metadata-version", args=["latest"]
        )
        try:
            yield send_pod_commissioning_results(
                client,
                pod.id,
                pod.name,
                pod.power_type,
                node.system_id,
                power_params,
                token.consumer.key,
                token.key,
                token.secret,
                urlparse(url),
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
            vmhost.get_power_parameters(),
            pod_id=vmhost.id,
            name=vmhost.name,
        )
        discovered_pod = get_best_discovered_result(discovered)
    except Exception as error:
        raise PodProblem(str(error)) from error

    if discovered_pod is None:
        raise PodProblem(
            "Unable to start the VM host discovery process. "
            "No rack controllers connected."
        )
    elif isinstance(discovered_pod, DiscoveredCluster):
        vmhost = sync_vmcluster(discovered_pod, discovered, vmhost, user)
    else:
        vmhost = _update_db(discovered_pod, discovered, vmhost, user)
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
        vmhost_power_parameters = await deferToDatabase(
            vmhost.get_power_parameters
        )
        discovered = await discover_pod(
            vmhost.power_type,
            vmhost_power_parameters,
            pod_id=vmhost.id,
            name=vmhost.name,
        )
        discovered_pod = get_best_discovered_result(discovered)
    except Exception as error:
        raise PodProblem(str(error)) from error

    if discovered_pod is None:
        raise PodProblem(
            "Unable to start the VM host discovery process. "
            "No rack controllers connected."
        )
    elif isinstance(discovered_pod, DiscoveredCluster):
        vmhost = await sync_vmcluster_async(
            discovered_pod, discovered, vmhost, user
        )
    else:
        await deferToDatabase(
            transactional(_update_db), discovered_pod, discovered, vmhost, user
        )
        await request_commissioning_results(vmhost)

    return vmhost


def _clean_power_address(vmhost_address):
    """Return clean power address

    XXX we assume a LXD host when connecting over
    HTTPS or the user omits the protocol. This MUST be
    generalized to support other services.
    """
    lxd_schemes = ["https", ""]

    # urlparse() doesn't work if scheme is missing
    if "://" not in vmhost_address:
        if (
            vmhost_address.count(":") > 1
            and "[" not in vmhost_address
            and "]" not in vmhost_address
        ):
            vmhost_address = f"[{vmhost_address}]"
        vmhost_address = f"{lxd_schemes[0]}://{vmhost_address}"

    vmhost_url = urlparse(vmhost_address)
    if vmhost_url.port:
        port = f":{vmhost_url.port}"
    else:
        port = ":8443" if vmhost_url.scheme in lxd_schemes else ""

    host = (
        f"[{vmhost_url.hostname}]"
        if valid_ipv6(vmhost_url.hostname)
        else vmhost_url.hostname
    )
    vmhost_url = vmhost_url._replace(netloc=f"{host}{port}")
    vmhost_address = vmhost_url.geturl()

    if vmhost_url.scheme in lxd_schemes:
        vmhost_address = vmhost_address.split("//")[-1]
    return vmhost_address


def _generate_cluster_power_params(vmhost, vmhost_address, first_host):
    new_params = first_host.get_power_parameters().copy()
    new_params["power_address"] = _clean_power_address(vmhost_address)
    if isinstance(vmhost, DiscoveredPod):
        new_params["instance_name"] = vmhost.name
    return new_params


def _get_or_create_clustered_host(
    cluster, discovered_vmhost, power_parameters
):
    host = None
    try:
        host = Pod.objects.get(
            name=discovered_vmhost.name,
            hints__cluster=cluster,
        )
    except Pod.DoesNotExist:
        host = create_pod(
            name=discovered_vmhost.name,
            architectures=discovered_vmhost.architectures,
            capabilities=discovered_vmhost.capabilities,
            version=discovered_vmhost.version,
            cores=discovered_vmhost.cores,
            cpu_speed=discovered_vmhost.cpu_speed,
            power_parameters=power_parameters,
            power_type="lxd",  # VM clusters are only supported in LXD
            zone=cluster.zone,
            pool=cluster.pool,
        )
    return host


def sync_vmcluster(discovered_cluster, discovered, vmhost, user):
    cluster, _ = VMCluster.objects.get_or_create(
        name=vmhost.cluster.name
        if vmhost.cluster
        else discovered_cluster.name or vmhost.name,
        project=discovered_cluster.project,
        pool=vmhost.pool,
        zone=vmhost.zone,
    )
    vmhost_pwr_addr = _clean_power_address(
        vmhost.get_power_parameters()["power_address"]
    )

    for i, discovered_vmhost in enumerate(discovered_cluster.pods):
        update_ret = False
        power_parameters = _generate_cluster_power_params(
            discovered_vmhost, discovered_cluster.pod_addresses[i], vmhost
        )
        if vmhost_pwr_addr != power_parameters["power_address"]:
            new_host = _get_or_create_clustered_host(
                cluster, discovered_vmhost, power_parameters
            )
        else:
            new_host = vmhost
            update_ret = True

        new_host = _update_db(
            discovered_vmhost, discovered, new_host, user, cluster
        )
        post_commit_do(
            reactor.callLater,
            0,
            request_commissioning_results,
            new_host,
        )
        if update_ret:
            vmhost = new_host

    return vmhost


async def sync_vmcluster_async(discovered_cluster, discovered, vmhost, user):
    def _transaction(discovered_cluster, discovered, vmhost, user):
        cluster, _ = VMCluster.objects.get_or_create(
            name=vmhost.hints.cluster.name
            if vmhost.cluster
            else discovered_cluster.name or vmhost.name,
            project=discovered_cluster.project,
            pool=vmhost.pool,
            zone=vmhost.zone,
        )
        new_hosts = []
        vmhost_pwr_addr = _clean_power_address(
            vmhost.get_power_parameters()["power_address"]
        )
        for i, discovered_vmhost in enumerate(discovered_cluster.pods):
            power_parameters = _generate_cluster_power_params(
                discovered, discovered_cluster.pod_addresses[i], vmhost
            )
            new_host = vmhost
            found = False
            if vmhost_pwr_addr != power_parameters["power_address"]:
                new_host = _get_or_create_clustered_host(
                    cluster, discovered_vmhost, power_parameters
                )
            else:
                new_host = vmhost
                found = True
            new_host = _update_db(
                discovered_vmhost, discovered, new_host, user, cluster
            )
            if found:
                new_hosts.insert(0, new_host)
            else:
                new_hosts.append(new_host)
        return new_hosts

    new_hosts = await deferToDatabase(
        transactional(_transaction),
        discovered_cluster,
        discovered,
        vmhost,
        user,
    )
    for new_host in new_hosts:
        await request_commissioning_results(new_host)
    return new_hosts[0]


def _update_db(discovered_pod, discovered, vmhost, user, cluster=None):
    vmhost.add_tag(ensure_pod_console_logging_tag().name)

    # If this is a new instance it will be stored in the database at the end of
    # sync.
    vmhost.sync(discovered_pod, user, cluster=cluster)

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
