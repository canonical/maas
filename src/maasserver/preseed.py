# Copyright 2012 Canonical Ltd.  This software is licensed under the
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
from os.path import join
from pipes import quote
from urllib import urlencode
from urlparse import urlparse

from curtin.pack import pack_install
from django.conf import settings
from maasserver.compose_preseed import (
    compose_cloud_init_preseed,
    compose_preseed,
    )
from maasserver.enum import (
    NODE_STATUS,
    PRESEED_TYPE,
    USERDATA_TYPE,
    )
from maasserver.models import Config
from maasserver.server_address import get_maas_facing_server_host
from maasserver.utils import absolute_reverse
from metadataserver.commissioning.snippets import get_snippet_context
from metadataserver.models import NodeKey
import tempita


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


def get_curtin_userdata(node):
    """Return the curtin user-data.

    :param node: The node for which to generate the user-data.
    :return: The rendered user-data string.
    :rtype: unicode.
    """
    installer_url = get_curtin_installer_url(node)
    config = get_curtin_config(node)
    return pack_install(configs=[config], args=[installer_url])


def get_curtin_installer_url(node):
    series = node.get_distro_series()
    context = get_preseed_context(series, node.nodegroup)
    cluster_host = context['cluster_host']
    # TODO: This shouldn't be hardcoded like that but rather synced
    # somehow with the content of contrib/maas-cluster-http.conf.
    return (
        "http://" + cluster_host + "/MAAS/static/images/" +
        node.architecture + "/" + series +
        "/xinstall/root.tar.gz")


def get_curtin_config(node):
    """Return the curtin configuration to be used by curtin.pack_install.

    :param node: The node for which to generate the configuration.
    :rtype: unicode.
    """
    series = node.get_distro_series()
    context = get_preseed_context(series, node.nodegroup)
    template = load_preseed_template(
        node, USERDATA_TYPE.CURTIN, series)
    context = get_preseed_context(series, nodegroup=node.nodegroup)
    context.update(get_node_preseed_context(node, series))
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
    return {
        'curtin_preseed': compose_cloud_init_preseed(token, base_url)
    }


def get_preseed_type_for(node):
    if node.should_use_traditional_installer():
        return PRESEED_TYPE.DEFAULT
    else:
        return PRESEED_TYPE.CURTIN


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
            release=Config.objects.get_config('commissioning_distro_series'))
    else:
        return render_preseed(
            node, get_preseed_type_for(node),
            release=node.get_distro_series())


def get_preseed_filenames(node, prefix='', release='', default=False):
    """List possible preseed template filenames for the given node.

    :param node: The node to return template preseed filenames for.
    :type node: :class:`maasserver.models.Node`
    :param prefix: At the top level, this is the preseed type (will be used as
        a prefix in the template filenames).  Usually one of {'', 'enlist',
        'commissioning'}.
    :type prefix: unicode
    :param release: The Ubuntu release to be used.
    :type release: unicode
    :param default: Should we return the default ('generic') template as a
        last resort template?
    :type default: boolean

    Returns a list of possible preseed template filenames using the following
    lookup order:
    {prefix}_{node_architecture}_{node_subarchitecture}_{release}_{node_name}
    {prefix}_{node_architecture}_{node_subarchitecture}_{release}
    {prefix}_{node_architecture}_{node_subarchitecture}
    {prefix}_{node_architecture}
    {prefix}
    'generic'
    """
    elements = []
    # Add prefix.
    if prefix != '':
        elements.append(prefix)
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
            filepath = join(location, filename)
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


def load_preseed_template(node, prefix, release=''):
    """Find and load a `PreseedTemplate` for the given node.

    :param node: See `get_preseed_filenames`.
    :param prefix: See `get_preseed_filenames`.
    :param release: See `get_preseed_filenames`.
    """

    def get_template(name, from_template, default=False):
        """A Tempita hook used to load the templates files.

        It is defined to preserve the context (node, name, release, default)
        since this will be called (by Tempita) called out of scope.
        """
        filenames = list(get_preseed_filenames(node, name, release, default))
        filepath, content = get_preseed_template(filenames)
        if filepath is None:
            raise TemplateNotFoundError(name)
        # This is where the closure happens: pass `get_template` when
        # instanciating PreseedTemplate.
        return PreseedTemplate(
            content, name=filepath, get_template=get_template)

    return get_template(prefix, None, default=True)


def get_hostname_and_path(url):
    """Return a tuple of the hostname and the hierarchical path from a url."""
    parsed_url = urlparse(url)
    return parsed_url.hostname, parsed_url.path


def get_preseed_context(release='', nodegroup=None):
    """Return the node-independent context dictionary to be used to render
    preseed templates.

    :param release: See `get_preseed_filenames`.
    :param nodegroup: The nodegroup used to generate the preseed.
    :return: The context dictionary.
    :rtype: dict.
    """
    server_host = get_maas_facing_server_host(nodegroup=nodegroup)
    main_archive_hostname, main_archive_directory = get_hostname_and_path(
        Config.objects.get_config('main_archive'))
    ports_archive_hostname, ports_archive_directory = get_hostname_and_path(
        Config.objects.get_config('ports_archive'))
    if nodegroup is None:
        base_url = None
        cluster_host = None
    else:
        base_url = nodegroup.maas_url
        cluster_if = nodegroup.get_managed_interface()
        any_cluster_if = nodegroup.get_any_interface()
        cluster_host = None
        if cluster_if is None:
            if any_cluster_if is not None:
                cluster_host = any_cluster_if.ip
        else:
            cluster_host = cluster_if.ip
    return {
        'main_archive_hostname': main_archive_hostname,
        'main_archive_directory': main_archive_directory,
        'ports_archive_hostname': ports_archive_hostname,
        'ports_archive_directory': ports_archive_directory,
        'release': release,
        'server_host': server_host,
        'server_url': absolute_reverse('nodes_handler', base_url=base_url),
        'metadata_enlist_url': absolute_reverse('enlist', base_url=base_url),
        'http_proxy': Config.objects.get_config('http_proxy'),
        'cluster_host': cluster_host,
        }


def get_node_preseed_context(node, release=''):
    """Return the node-dependent context dictionary to be used to render
    preseed templates.

    :param node: See `get_preseed_filenames`.
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
    return {
        'node': node,
        'preseed_data': compose_preseed(node),
        'node_disable_pxe_url': node_disable_pxe_url,
        'node_disable_pxe_data': node_disable_pxe_data,
    }


def render_enlistment_preseed(prefix, release='', nodegroup=None):
    """Return the enlistment preseed.

    :param prefix: See `get_preseed_filenames`.
    :param release: See `get_preseed_filenames`.
    :param nodegroup: The nodegroup used to generate the preseed.
    :return: The rendered preseed string.
    :rtype: unicode.
    """
    template = load_preseed_template(None, prefix, release)
    context = get_preseed_context(release, nodegroup=nodegroup)
    # Render the snippets in the main template.
    snippets = get_snippet_context()
    snippets.update(context)
    return template.substitute(**snippets)


def render_preseed(node, prefix, release=''):
    """Return the preseed for the given node.

    :param node: See `get_preseed_filenames`.
    :param prefix: See `get_preseed_filenames`.
    :param release: See `get_preseed_filenames`.
    :return: The rendered preseed string.
    :rtype: unicode.
    """
    template = load_preseed_template(node, prefix, release)
    nodegroup = node.nodegroup
    context = get_preseed_context(release, nodegroup=nodegroup)
    context.update(get_node_preseed_context(node, release))
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
