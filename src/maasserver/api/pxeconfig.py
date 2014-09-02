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

from django.http import HttpResponse
from maasserver.api.utils import (
    get_mandatory_param,
    get_optional_param,
    )
from maasserver.enum import (
    NODE_STATUS,
    PRESEED_TYPE,
    )
from maasserver.models import (
    BootImage,
    Config,
    MACAddress,
    NodeGroup,
    )
from maasserver.preseed import (
    compose_enlistment_preseed_url,
    compose_preseed_url,
    get_preseed_type_for,
    )
from maasserver.server_address import get_maas_facing_server_address
from maasserver.third_party_drivers import get_third_party_driver
from maasserver.utils import (
    find_nodegroup,
    strip_domain,
    )
from maasserver.utils.orm import get_one
from provisioningserver.kernel_opts import KernelParameters
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


def get_boot_purpose(node):
    """Return a suitable "purpose" for this boot, e.g. "install"."""
    # XXX: allenap bug=1031406 2012-07-31: The boot purpose is still in
    # flux. It may be that there will just be an "ephemeral" environment and
    # an "install" environment, and the differing behaviour between, say,
    # enlistment and commissioning - both of which will use the "ephemeral"
    # environment - will be governed by varying the preseed or PXE
    # configuration.
    if node is None:
        # This node is enlisting, for which we use a commissioning image.
        return "commissioning"
    elif node.status == NODE_STATUS.COMMISSIONING:
        # It is commissioning.
        return "commissioning"
    elif node.status == NODE_STATUS.DEPLOYING:
        # Install the node if netboot is enabled, otherwise boot locally.
        if node.netboot:
            preseed_type = get_preseed_type_for(node)
            if preseed_type == PRESEED_TYPE.CURTIN:
                return "xinstall"
            else:
                return "install"
        else:
            return "local"  # TODO: Investigate.
    elif node.status == NODE_STATUS.DEPLOYED:
        return "local"
    else:
        # Just poweroff? TODO: Investigate. Perhaps even send an IPMI signal
        # to turn off power.
        return "poweroff"


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
    node = get_node_from_mac_string(request.GET.get('mac', None))

    if node is None or node.status == NODE_STATUS.COMMISSIONING:
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
                # Look in BootImage for an image that actually exists for the
                # current series. If nothing is found, fall back to i386 like
                # we used to. LP #1181334
                image = BootImage.objects.get_default_arch_image_in_nodegroup(
                    nodegroup, osystem, series, purpose='commissioning')
                if image is None:
                    arch = 'i386'
                else:
                    arch = image.architecture

        subarch = get_optional_param(request.GET, 'subarch', 'generic')

    # If we are booting with "xinstall", then we should always return the
    # commissioning operating system and distro_series.
    purpose = get_boot_purpose(node)
    if purpose == "xinstall":
        osystem = Config.objects.get_config('commissioning_osystem')
        series = Config.objects.get_config('commissioning_distro_series')

    # We use as our default label the label of the most recent image for
    # the criteria we've assembled above. If there is no latest image
    # (which should never happen in reality but may happen in tests), we
    # fall back to using 'no-such-image' as our default.
    latest_image = BootImage.objects.get_latest_image(
        nodegroup, osystem, arch, subarch, series, purpose)
    if latest_image is None:
        # XXX 2014-03-18 gmb bug=1294131:
        #     We really ought to raise an exception here so that client
        #     and server can handle it according to their needs. At the
        #     moment, though, that breaks too many tests in awkward
        #     ways.
        latest_label = 'no-such-image'
    else:
        latest_label = latest_image.label
        # subarch may be different from the request because newer images
        # support older hardware enablement, e.g. trusty/generic
        # supports trusty/hwe-s. We must override the subarch to the one
        # on the image otherwise the config path will be wrong if
        # get_latest_image() returned an image with a different subarch.
        subarch = latest_image.subarchitecture
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
        label=label, purpose=purpose, hostname=hostname, domain=domain,
        preseed_url=preseed_url, log_host=server_address,
        fs_host=cluster_address, extra_opts=extra_kernel_opts)

    return HttpResponse(
        json.dumps(params._asdict()),
        content_type="application/json")
