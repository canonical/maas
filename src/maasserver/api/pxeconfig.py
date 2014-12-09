# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handler: `pxeconfig`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'pxeconfig',
    ]


import httplib

from crochet import TimeoutError
from django.http import HttpResponse
from maasserver import logger
from maasserver.api.utils import (
    get_mandatory_param,
    get_optional_param,
    )
from maasserver.clusterrpc.boot_images import get_boot_images_for
from maasserver.models import (
    BootResource,
    Config,
    Event,
    MACAddress,
    NodeGroup,
    )
from maasserver.models.macaddress import update_mac_cluster_interfaces
from maasserver.preseed import (
    compose_enlistment_preseed_url,
    compose_preseed_url,
    )
from maasserver.server_address import get_maas_facing_server_address
from maasserver.third_party_drivers import get_third_party_driver
from maasserver.utils import (
    find_nodegroup,
    strip_domain,
    )
from maasserver.utils.orm import get_one
from provisioningserver.events import EVENT_TYPES
from provisioningserver.kernel_opts import KernelParameters
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
import simplejson as json


def find_nodegroup_for_pxeconfig_request(request):
    """Find the nodegroup responsible for a `pxeconfig` request.

    Looks for the `cluster_uuid` parameter in the request.  If there is
    none, figures it out based on the requesting IP as a compatibility
    measure.  In that case, the result may be incorrect.
    """
    uuid = request.GET.get('cluster_uuid', None)
    if uuid is None:
        return find_nodegroup(request)
    else:
        return NodeGroup.objects.get(uuid=uuid)


def get_node_from_mac_string(mac_string):
    """Get a Node object from a MAC address string.

    Returns a Node object or None if no node with the given MAC address exists.

    :param mac_string: MAC address string in the form "12-34-56-78-9a-bc"
    :return: Node object or None
    """
    if mac_string is None:
        return None
    macaddress = get_one(MACAddress.objects.filter(mac_address=mac_string))
    return macaddress.node if macaddress else None


def get_boot_image(
        nodegroup, osystem, architecture, subarchitecture, series, purpose):
    """Obtain the first available boot image for this cluster for the given
    osystem, architecture, subarchitecute, series, and purpose."""
    # When local booting a node we put it through a PXE cycle. In
    # this case it requests a purpose of "local" when looking for
    # boot images.  To avoid unnecessary work, we can shortcut that
    # here and just return None right away.
    if purpose == "local":
        return None

    try:
        images = get_boot_images_for(
            nodegroup, osystem, architecture, subarchitecture, series)
    except (NoConnectionsAvailable, TimeoutError):
        logger.error(
            "Unable to identify boot image for (%s/%s/%s/%s/%s): "
            "no RPC connection to cluster '%s'",
            osystem, architecture, subarchitecture, series, purpose,
            nodegroup.name)
        return None
    for image in images:
        # get_boot_images_for returns all images that match the subarchitecure
        # and its supporting subarches. Only want to return the image with
        # the exact subarchitecture.
        if (image['subarchitecture'] == subarchitecture and
                image['purpose'] == purpose):
            return image
    logger.error(
        "Unable to identify boot image for (%s/%s/%s/%s/%s): "
        "cluster '%s' does not have matching boot image.",
        osystem, architecture, subarchitecture, series, purpose,
        nodegroup.name)
    return None


# XXX newell 2014-10-01 bug=1376489: Currently logging the pxe
# request for the given boot purpose here. It would be better to
# someday fix this to create the log entries when the file
# transfer completes, rather than when we receive the first
# (and potentially duplicate) packet of the request.
def event_log_pxe_request(node, purpose):
    """Log PXE request to node's event log."""
    options = {
        'commissioning': "commissioning",
        'xinstall': "curtin install",
        'install': "d-i install",
        'local': "local boot",
        'poweroff': "power off",
    }
    Event.objects.create_node_event(
        system_id=node.system_id, event_type=EVENT_TYPES.NODE_PXE_REQUEST,
        event_description=options[purpose])


def pxeconfig(request):
    """Get the PXE configuration given a node's details.

    Returns a JSON object corresponding to a
    :class:`provisioningserver.kernel_opts.KernelParameters` instance.

    This is now fairly decoupled from pxelinux's TFTP filename encoding
    mechanism, with one notable exception. Call this function with (mac, arch,
    subarch) and it will do the right thing. If details it needs are missing
    (ie. arch/subarch missing when the MAC is supplied but unknown), then it
    will as an exception return an HTTP NO_CONTENT (204) in the expectation
    that this will be translated to a TFTP file not found and pxelinux (or an
    emulator) will fall back to default-<arch>-<subarch> (in the case of an
    alternate architecture emulator) or just straight to default (in the case
    of native pxelinux on i386 or amd64). See bug 1041092 for details and
    discussion.

    :param mac: MAC address to produce a boot configuration for.
    :param arch: Architecture name (in the pxelinux namespace, eg. 'arm' not
        'armhf').
    :param subarch: Subarchitecture name (in the pxelinux namespace).
    :param local: The IP address of the cluster controller.
    :param remote: The IP address of the booting node.
    :param cluster_uuid: UUID of the cluster responsible for this node.
        If omitted, the call will attempt to figure it out based on the
        requesting IP address, for compatibility.  Passing `cluster_uuid`
        is preferred.
    """
    request_mac = request.GET.get('mac', None)
    request_ip = request.GET.get('remote', None)
    node = get_node_from_mac_string(request_mac)

    if node is not None:
        # Update the record of which MAC address and cluster interface
        # this node uses to PXE boot.
        node.pxe_mac = MACAddress.objects.get(mac_address=request_mac)
        node.save()
        update_mac_cluster_interfaces(request_ip, request_mac, node.nodegroup)

    if node is None or node.get_boot_purpose() == "commissioning":
        osystem = Config.objects.get_config('commissioning_osystem')
        series = Config.objects.get_config('commissioning_distro_series')
    else:
        osystem = node.get_osystem()
        series = node.get_distro_series()

    if node:
        arch, subarch = node.architecture.split('/')
        preseed_url = compose_preseed_url(node)
        # The node's hostname may include a domain, but we ignore that
        # and use the one from the nodegroup instead.
        hostname = strip_domain(node.hostname)
        nodegroup = node.nodegroup
        domain = nodegroup.name
    else:
        nodegroup = find_nodegroup_for_pxeconfig_request(request)
        preseed_url = compose_enlistment_preseed_url(nodegroup=nodegroup)
        hostname = 'maas-enlist'
        domain = Config.objects.get_config('enlistment_domain')

        arch = get_optional_param(request.GET, 'arch')
        if arch is None:
            if 'mac' in request.GET:
                # Request was pxelinux.cfg/01-<mac>, so attempt fall back
                # to pxelinux.cfg/default-<arch>-<subarch> for arch detection.
                return HttpResponse(status=httplib.NO_CONTENT)
            else:
                # Look in BootResource for an resource that actually exists for
                # the current series. If nothing is found, fall back to i386
                # like we used to. LP #1181334
                resource = (
                    BootResource.objects.get_default_commissioning_resource(
                        osystem, series))
                if resource is None:
                    arch = 'i386'
                else:
                    arch, _ = resource.split_arch()

        subarch = get_optional_param(request.GET, 'subarch', 'generic')

    # If we are booting with "xinstall", then we should always return the
    # commissioning operating system and distro_series.
    if node is None:
        purpose = "commissioning"  # enlistment
    else:
        purpose = node.get_boot_purpose()
        event_log_pxe_request(node, purpose)

    # Use only the commissioning osystem and series, for operating systems
    # other than Ubuntu. As Ubuntu supports HWE kernels, and needs to use
    # that kernel to perform the installation.
    if purpose == "xinstall" and osystem != 'ubuntu':
        osystem = Config.objects.get_config('commissioning_osystem')
        series = Config.objects.get_config('commissioning_distro_series')

    if purpose == 'poweroff':
        # In order to power the node off, we need to get it booted in the
        # commissioning environment and issue a `poweroff` command.
        boot_purpose = 'commissioning'
    else:
        boot_purpose = purpose

    # We use as our default label the label of the most recent image for
    # the criteria we've assembled above. If there is no latest image
    # (which should never happen in reality but may happen in tests), we
    # fall back to using 'no-such-image' as our default.
    latest_image = get_boot_image(
        nodegroup, osystem, arch, subarch, series, boot_purpose)
    if latest_image is None:
        # XXX 2014-03-18 gmb bug=1294131:
        #     We really ought to raise an exception here so that client
        #     and server can handle it according to their needs. At the
        #     moment, though, that breaks too many tests in awkward
        #     ways.
        latest_label = 'no-such-image'
    else:
        latest_label = latest_image['label']
        # subarch may be different from the request because newer images
        # support older hardware enablement, e.g. trusty/generic
        # supports trusty/hwe-s. We must override the subarch to the one
        # on the image otherwise the config path will be wrong if
        # get_latest_image() returned an image with a different subarch.
        subarch = latest_image['subarchitecture']
    label = get_optional_param(request.GET, 'label', latest_label)

    if node is not None:
        # We don't care if the kernel opts is from the global setting or a tag,
        # just get the options
        _, effective_kernel_opts = node.get_effective_kernel_options()

        # Add any extra options from a third party driver.
        use_driver = Config.objects.get_config('enable_third_party_drivers')
        if use_driver:
            driver = get_third_party_driver(node)
            driver_kernel_opts = driver.get('kernel_opts', '')

            combined_opts = ('%s %s' % (
                '' if effective_kernel_opts is None else effective_kernel_opts,
                driver_kernel_opts)).strip()
            if len(combined_opts):
                extra_kernel_opts = combined_opts
            else:
                extra_kernel_opts = None
        else:
            extra_kernel_opts = effective_kernel_opts
    else:
        # If there's no node defined then we must be enlisting here, but
        # we still need to return the global kernel options.
        extra_kernel_opts = Config.objects.get_config("kernel_opts")

    server_address = get_maas_facing_server_address(nodegroup=nodegroup)
    cluster_address = get_mandatory_param(request.GET, "local")

    params = KernelParameters(
        osystem=osystem, arch=arch, subarch=subarch, release=series,
        label=label, purpose=boot_purpose, hostname=hostname, domain=domain,
        preseed_url=preseed_url, log_host=server_address,
        fs_host=cluster_address, extra_opts=extra_kernel_opts)

    return HttpResponse(
        json.dumps(params._asdict()),
        content_type="application/json")
