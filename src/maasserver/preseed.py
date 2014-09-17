# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Preseed generation."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'compose_enlistment_preseed_url',
    'compose_preseed_url',
    'get_curtin_userdata',
    'get_enlist_preseed',
    'get_preseed',
    'get_preseed_context',
    ]

from collections import namedtuple
import os.path
from pipes import quote
from urllib import urlencode
from urlparse import urlparse

from crochet import TimeoutError
from curtin.pack import pack_install
from django.conf import settings
from maasserver import logger
from maasserver.clusterrpc.boot_images import get_boot_images_for
from maasserver.compose_preseed import (
    compose_cloud_init_preseed,
    compose_preseed,
    )
from maasserver.enum import (
    NODE_BOOT,
    NODE_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    PRESEED_TYPE,
    USERDATA_TYPE,
    )
from maasserver.exceptions import (
    ClusterUnavailable,
    MissingBootImage,
    PreseedError,
    )
from maasserver.models import (
    Config,
    DHCPLease,
    )
from maasserver.server_address import get_maas_facing_server_host
from maasserver.third_party_drivers import get_third_party_driver
from maasserver.utils import absolute_reverse
from metadataserver.commissioning.snippets import get_snippet_context
from metadataserver.models import NodeKey
from netaddr import IPAddress
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.utils import (
    compose_URL,
    locate_config,
    )
from provisioningserver.utils.fs import read_text_file
import tempita
import yaml


GENERIC_FILENAME = 'generic'


def get_enlist_preseed(nodegroup=None):
    """Return the enlistment preseed.

    :param nodegroup: The nodegroup used to generate the preseed.
    :return: The rendered preseed string.
    :rtype: unicode.
    """
    return render_enlistment_preseed(
        PRESEED_TYPE.ENLIST, nodegroup=nodegroup)


def get_enlist_userdata(nodegroup=None):
    """Return the enlistment preseed.

    :param nodegroup: The nodegroup used to generate the preseed.
    :return: The rendered enlistment user-data string.
    :rtype: unicode.
    """
    return render_enlistment_preseed(
        USERDATA_TYPE.ENLIST, nodegroup=nodegroup)


def list_gateways_and_macs(node):
    """Return a node's router addresses, as a set of IP/MAC pairs.

    In each returned pair, the MAC address is that of a network interface
    on the node.  The IP address is a router address for that interface.
    """
    result = set()
    for mac in node.macaddress_set.filter(cluster_interface__isnull=False):
        for cluster_interface in mac.get_cluster_interfaces():
            if cluster_interface.router_ip not in (None, ''):
                result.add((cluster_interface.router_ip, mac.mac_address))
    return result


def compose_curtin_network_preseed(node):
    """Return a list of curtin preseeds for configuring a node's networking.

    These can then be appended to the main Curtin configuration.  The preseeds
    are returned as a list of strings, each holding a YAML section.

    The configuration currently only sets static IPv6 addresses, by uploading
    the `maas_configure_interfaces` script to the node during installation, and
    running it.
    """
    # Read the script that we will run on the node.  It really isn't a
    # template; it's a simple Python module and it has tests.
    script = locate_config(
        'templates/deployment-user-data/maas_configure_interfaces.py')

    # Deal with transitional issue: the packaging doesn't install this script
    # just yet.  Once the packaging has been updated, we can just assume that
    # the file is present.
    if not os.path.isfile(script):
        return []

    configure_script = read_text_file(script)

    # Preseed: upload the script to the node's installed filesystem.
    write_files = {
        'write_files': {
            'maas_configure_interfaces': {
                'path': '/usr/local/bin/maas_configure_interfaces.py',
                'owner': 'root:root',
                'permissions': '0755',
                'content': configure_script,
                },
            },
        }
    # Compile static IPv6 addresses to be passed to the script.
    static_ip_args = [
        '--static-ip=%s=%s' % (ip, mac)
        for ip, mac in node.get_static_ip_mappings()
        if IPAddress(ip).version == 6
        ]
    # Compile IPv6 gateway addresses to be passed to the script.
    gateway_args = [
        '--gateway=%s=%s' % (gateway, mac)
        for gateway, mac in list_gateways_and_macs(node)
        if IPAddress(gateway).version == 6
        ]
    # Preseed: run the script, from within the installed filesystem.
    configure = {
        'late_commands': {
            '90_maas_configure_interfaces': [
                'curtin',
                'in-target',
                '--',
                '/usr/local/bin/maas_configure_interfaces.py',
                '--update-interfaces',
                ] + static_ip_args + gateway_args,
            },
        }
    return [yaml.safe_dump(write_files), yaml.safe_dump(configure)]


def get_curtin_userdata(node):
    """Return the curtin user-data.

    :param node: The node for which to generate the user-data.
    :return: The rendered user-data string.
    :rtype: unicode.
    """
    installer_url = get_curtin_installer_url(node)
    main_config = get_curtin_config(node)
    network_config = compose_curtin_network_preseed(node)
    return pack_install(
        configs=[main_config] + network_config, args=[installer_url])


def get_curtin_image(node):
    """Return boot image that supports 'xinstall' for the given node."""
    osystem = node.get_osystem()
    series = node.get_distro_series()
    arch, subarch = node.split_arch()
    try:
        images = get_boot_images_for(
            node.nodegroup, osystem, arch, subarch, series)
    except (NoConnectionsAvailable, TimeoutError):
        logger.error(
            "Unable to get RPC connection for cluster '%s'",
            node.nodegroup.name)
        raise ClusterUnavailable(
            "Unable to get RPC connection for cluster '%s'" % (
                node.nodegroup.name))
    for image in images:
        if image['purpose'] == 'xinstall':
            return image
    raise MissingBootImage(
        "Error generating the URL of curtin's image file.  "
        "No image could be found for the given selection: "
        "os=%s, arch=%s, subarch=%s, series=%s, purpose=xinstall." % (
            osystem,
            arch,
            subarch,
            series,
        ))


def get_curtin_installer_url(node):
    """Return the URL where curtin on the node can download its installer."""
    osystem = node.get_osystem()
    series = node.get_distro_series()
    arch, subarch = node.architecture.split('/')
    cluster_host = pick_cluster_controller_address(node)
    # XXX rvb(?): The path shouldn't be hardcoded like this, but rather synced
    # somehow with the content of contrib/maas-cluster-http.conf.
    image = get_curtin_image(node)
    if image['xinstall_type'] == 'tgz':
        url_prepend = ''
    else:
        url_prepend = '%s:' % image['xinstall_type']
    dyn_uri = '/'.join([
        osystem,
        arch,
        subarch,
        series,
        image['label'],
        image['xinstall_path'],
        ])
    url = compose_URL(
        'http:///MAAS/static/images/%s' % dyn_uri, cluster_host)
    return url_prepend + url


def get_curtin_config(node):
    """Return the curtin configuration to be used by curtin.pack_install.

    :param node: The node for which to generate the configuration.
    :rtype: unicode.
    """
    osystem = node.get_osystem()
    series = node.get_distro_series()
    template = load_preseed_template(
        node, USERDATA_TYPE.CURTIN, osystem, series)
    context = get_preseed_context(osystem, series, nodegroup=node.nodegroup)
    context.update(get_node_preseed_context(node, osystem, series))
    context.update(get_curtin_context(node))

    return template.substitute(**context)


def get_curtin_context(node):
    """Return the curtin-specific context dictionary to be used to render
    user-data templates.

    :param node: The node for which to generate the user-data.
    :rtype: dict.
    """
    token = NodeKey.objects.get_token_for_node(node)
    base_url = node.nodegroup.maas_url
    version = 'latest'
    return {
        'reporter_token': token,
        'reporter_url': absolute_reverse(
            'curtin-metadata-version', args=[version],
            query={'op': 'signal'}, base_url=base_url),
        'curtin_preseed': compose_cloud_init_preseed(token, base_url)
    }


def get_supported_purposes_for_node(node):
    """Return all purposes the node currently supports based on its
    os, architecture, and series."""
    os_name = node.get_osystem()
    series = node.get_distro_series()
    arch, subarch = node.split_arch()
    try:
        images = get_boot_images_for(
            node.nodegroup, os_name, arch, subarch, series)
    except (NoConnectionsAvailable, TimeoutError):
        logger.error(
            "Unable to get RPC connection for cluster '%s'",
            node.nodegroup.name)
        raise ClusterUnavailable(
            "Unable to get RPC connection for cluster '%s'" % (
                node.nodegroup.name))
    return {image['purpose'] for image in images}


def get_available_purpose_for_node(purposes, node):
    """Return the best available purpose for the given purposes and images."""
    supported_purposes = get_supported_purposes_for_node(node)
    for purpose in purposes:
        if purpose in supported_purposes:
            return purpose
    logger.error(
        "Unable to determine purpose for node: '%s'", node.fqdn)
    raise PreseedError(
        "Unable to determine purpose for node: '%s'", node.fqdn)


def get_preseed_type_for(node):
    """Returns the preseed type for the node.

    This is determined using the nodes boot_type and what supporting boot
    images exist on the node's cluster. If the node is to boot using
    fast-path installer, but there is no boot image that supports this
    method then the default installer will be used. If the node is to boot
    using the default installer but there is no boot image that supports
    that method then it will boot using the fast-path installer.
    """
    if node.status == NODE_STATUS.COMMISSIONING:
        return PRESEED_TYPE.COMMISSIONING
    if node.boot_type == NODE_BOOT.FASTPATH:
        purpose_order = ['xinstall', 'install']
    elif node.boot_type == NODE_BOOT.DEBIAN:
        purpose_order = ['install', 'xinstall']
    else:
        purpose_order = []

    purpose = get_available_purpose_for_node(purpose_order, node)
    if purpose == 'xinstall':
        return PRESEED_TYPE.CURTIN
    elif purpose == 'install':
        return PRESEED_TYPE.DEFAULT
    logger.error(
        "Unknown purpose '%s' for node: '%s'", purpose, node.fqdn)
    raise PreseedError(
        "Unknown purpose '%s' for node: '%s'", purpose, node.fqdn)


def get_preseed(node):
    """Return the preseed for a given node.  Depending on the node's status
    this will be a commissioning preseed (if the node is commissioning) or an
    install preseed (normal installation preseed or curtin preseed).

    :param node: The node to return preseed for.
    :type node: :class:`maasserver.models.Node`
    :return: The rendered preseed string.
    :rtype: unicode.
    """
    if node.status == NODE_STATUS.COMMISSIONING:
        return render_preseed(
            node, PRESEED_TYPE.COMMISSIONING,
            osystem=Config.objects.get_config('commissioning_osystem'),
            release=Config.objects.get_config('commissioning_distro_series'))
    else:
        return render_preseed(
            node, get_preseed_type_for(node),
            osystem=node.get_osystem(), release=node.get_distro_series())


def get_preseed_filenames(node, prefix='', osystem='', release='',
                          default=False):
    """List possible preseed template filenames for the given node.

    :param node: The node to return template preseed filenames for.
    :type node: :class:`maasserver.models.Node`
    :param prefix: At the top level, this is the preseed type (will be used as
        a prefix in the template filenames).  Usually one of {'', 'enlist',
        'commissioning'}.
    :type prefix: unicode
    :param osystem: The operating system to be used.
    :type osystem: unicode
    :param release: The os release to be used.
    :type release: unicode
    :param default: Should we return the default ('generic') template as a
        last resort template?
    :type default: boolean

    Returns a list of possible preseed template filenames using the following
    lookup order:
    {prefix}_{osystem}_{node_arch}_{node_subarch}_{release}_{node_name}
    {prefix}_{osystem}_{node_arch}_{node_subarch}_{release}
    {prefix}_{osystem}_{node_arch}_{node_subarch}
    {prefix}_{osystem}_{node_arch}
    {prefix}_{osystem}
    {prefix}
    'generic'
    """
    elements = []
    # Add prefix.
    if prefix != '':
        elements.append(prefix)
    # Add osystem
    elements.append(osystem)
    # Add architecture/sub-architecture.
    if node is not None:
        arch = split_subarch(node.architecture)
        elements.extend(arch)
    # Add release.
    elements.append(release)
    # Add hostname.
    if node is not None:
        elements.append(node.hostname)
    while elements:
        yield compose_filename(elements)
        elements.pop()
    if default:
        yield GENERIC_FILENAME


def split_subarch(architecture):
    """Split the architecture and the subarchitecture."""
    return architecture.split('/')


def compose_filename(elements):
    """Create a preseed filename from a list of elements."""
    return '_'.join(elements)


def get_preseed_template(filenames):
    """Get the path and content for the first template found.

    :param filenames: An iterable of relative filenames.
    """
    assert not isinstance(filenames, (bytes, unicode))
    assert all(isinstance(filename, unicode) for filename in filenames)
    for location in settings.PRESEED_TEMPLATE_LOCATIONS:
        for filename in filenames:
            filepath = os.path.join(location, filename)
            try:
                with open(filepath, "rb") as stream:
                    content = stream.read()
                    return filepath, content
            except IOError:
                pass  # Ignore.
    else:
        return None, None


def get_escape_singleton():
    """Return a singleton containing methods to escape various formats used in
    the preseed templates.
    """
    Escape = namedtuple('Escape', 'shell')
    return Escape(shell=quote)


class PreseedTemplate(tempita.Template):
    """A Tempita template specialised for preseed rendering.

    It provides a filter named 'escape' which contains methods to escape
    various formats used in the template."""

    default_namespace = dict(
        tempita.Template.default_namespace,
        escape=get_escape_singleton())


class TemplateNotFoundError(Exception):
    """The template has not been found."""

    def __init__(self, name):
        super(TemplateNotFoundError, self).__init__(name)
        self.name = name


def load_preseed_template(node, prefix, osystem='', release=''):
    """Find and load a `PreseedTemplate` for the given node.

    :param node: See `get_preseed_filenames`.
    :param prefix: See `get_preseed_filenames`.
    :param osystem: See `get_preseed_filenames`.
    :param release: See `get_preseed_filenames`.
    """

    def get_template(name, from_template, default=False):
        """A Tempita hook used to load the templates files.

        It is defined to preserve the context (node, name, release, default)
        since this will be called (by Tempita) called out of scope.
        """
        filenames = list(get_preseed_filenames(
            node, name, osystem, release, default))
        filepath, content = get_preseed_template(filenames)
        if filepath is None:
            raise TemplateNotFoundError(name)
        # This is where the closure happens: pass `get_template` when
        # instanciating PreseedTemplate.
        return PreseedTemplate(
            content, name=filepath, get_template=get_template)

    return get_template(prefix, None, default=True)


def get_netloc_and_path(url):
    """Return a tuple of the netloc and the hierarchical path from a url.

    The netloc, the "Network location part", is composed of the hostname
    and, optionally, the port.
    """
    parsed_url = urlparse(url)
    return parsed_url.netloc, parsed_url.path


def pick_cluster_controller_address(node):
    """Return an IP address for the cluster controller, to be used by `node`.

    Curtin, running on the nodes, will download its installer image from here.
    It will look for an address on a network to which `node` is connected, or
    failing that, it will prefer a managed interface over an unmanaged one.
    """
    # Sort interfaces by desirability, so we can pick the first one.
    unmanaged = NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED
    sort_key = lambda interface: (
        # Put unmanaged interfaces at the end as a last resort.
        1 if interface.management == unmanaged else 0,
        # Sort by ID as a tie-breaker, for consistency.
        interface.id,
        )
    interfaces = sorted(
        node.nodegroup.nodegroupinterface_set.all(), key=sort_key)
    macs = [mac.mac_address for mac in node.macaddress_set.all()]
    node_ips = [
        IPAddress(ip)
        for ip in DHCPLease.objects.filter(mac__in=macs).values_list(
            'ip', flat=True)
        ]
    # Search cluster controller's interfaces for a network that encompasses
    # any of the node's IP addresses.
    for interface in interfaces:
        network = interface.network
        for node_ip in node_ips:
            if node_ip in network:
                return interface.ip
    # None found: pick the best guess, if available.
    if interfaces == []:
        return None
    else:
        return interfaces[0].ip


def get_preseed_context(osystem='', release='', nodegroup=None):
    """Return the node-independent context dictionary to be used to render
    preseed templates.

    :param osystem: See `get_preseed_filenames`.
    :param release: See `get_preseed_filenames`.
    :param nodegroup: The nodegroup used to generate the preseed.
    :return: The context dictionary.
    :rtype: dict.
    """
    server_host = get_maas_facing_server_host(nodegroup=nodegroup)
    main_archive_hostname, main_archive_directory = get_netloc_and_path(
        Config.objects.get_config('main_archive'))
    ports_archive_hostname, ports_archive_directory = get_netloc_and_path(
        Config.objects.get_config('ports_archive'))
    if nodegroup is None:
        base_url = None
    else:
        base_url = nodegroup.maas_url
    return {
        'main_archive_hostname': main_archive_hostname,
        'main_archive_directory': main_archive_directory,
        'ports_archive_hostname': ports_archive_hostname,
        'ports_archive_directory': ports_archive_directory,
        'osystem': osystem,
        'release': release,
        'server_host': server_host,
        'server_url': absolute_reverse('nodes_handler', base_url=base_url),
        'metadata_enlist_url': absolute_reverse('enlist', base_url=base_url),
        'http_proxy': Config.objects.get_config('http_proxy'),
        }


def get_node_preseed_context(node, osystem='', release=''):
    """Return the node-dependent context dictionary to be used to render
    preseed templates.

    :param node: See `get_preseed_filenames`.
    :param osystem: See `get_preseed_filenames`.
    :param release: See `get_preseed_filenames`.
    :return: The context dictionary.
    :rtype: dict.
    """
    # Create the url and the url-data (POST parameters) used to turn off
    # PXE booting once the install of the node is finished.
    node_disable_pxe_url = absolute_reverse(
        'metadata-node-by-id', args=['latest', node.system_id],
        base_url=node.nodegroup.maas_url)
    node_disable_pxe_data = urlencode({'op': 'netboot_off'})
    driver = get_third_party_driver(node)
    return {
        'third_party_drivers': (
            Config.objects.get_config('enable_third_party_drivers')),
        'driver': driver,
        'driver_package': driver.get('package', ''),
        'node': node,
        'preseed_data': compose_preseed(get_preseed_type_for(node), node),
        'node_disable_pxe_url': node_disable_pxe_url,
        'node_disable_pxe_data': node_disable_pxe_data,
        'license_key': node.get_effective_license_key(),
    }


def render_enlistment_preseed(prefix, osystem='', release='', nodegroup=None):
    """Return the enlistment preseed.

    :param prefix: See `get_preseed_filenames`.
    :param osystem: See `get_preseed_filenames`.
    :param release: See `get_preseed_filenames`.
    :param nodegroup: The nodegroup used to generate the preseed.
    :return: The rendered preseed string.
    :rtype: unicode.
    """
    template = load_preseed_template(None, prefix, osystem, release)
    context = get_preseed_context(osystem, release, nodegroup=nodegroup)
    # Render the snippets in the main template.
    snippets = get_snippet_context()
    snippets.update(context)
    return template.substitute(**snippets)


def render_preseed(node, prefix, osystem='', release=''):
    """Return the preseed for the given node.

    :param node: See `get_preseed_filenames`.
    :param prefix: See `get_preseed_filenames`.
    :param osystem: See `get_preseed_filenames`.
    :param release: See `get_preseed_filenames`.
    :return: The rendered preseed string.
    :rtype: unicode.
    """
    template = load_preseed_template(node, prefix, osystem, release)
    nodegroup = node.nodegroup
    context = get_preseed_context(osystem, release, nodegroup=nodegroup)
    context.update(get_node_preseed_context(node, osystem, release))
    return template.substitute(**context)


def compose_enlistment_preseed_url(nodegroup=None):
    """Compose enlistment preseed URL.

    :param nodegroup: The nodegroup used to generate the preseed.
    """
    # Always uses the latest version of the metadata API.
    base_url = nodegroup.maas_url if nodegroup is not None else None
    version = 'latest'
    return absolute_reverse(
        'metadata-enlist-preseed', args=[version],
        query={'op': 'get_enlist_preseed'}, base_url=base_url)


def compose_preseed_url(node):
    """Compose a metadata URL for `node`'s preseed data."""
    # Always uses the latest version of the metadata API.
    version = 'latest'
    base_url = node.nodegroup.maas_url
    return absolute_reverse(
        'metadata-node-by-id', args=[version, node.system_id],
        query={'op': 'get_preseed'}, base_url=base_url)
