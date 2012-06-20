# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Preseed generation."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from os.path import join
from urlparse import urlparse

from django.conf import settings
from maasserver.models import Config
from maasserver.provisioning import compose_preseed
import tempita


GENERIC_FILENAME = 'generic'


# XXX: rvb 2012-06-14 bug=1013146:  'precise' is hardcoded here.
def get_preseed_filenames(node, prefix='', release='precise', default=False):
    """List possible preseed template filenames for the given node.

    :param node: The node to return template preseed filenames for.
    :type node: :class:`maasserver.models.Node`
    :param prefix: At the top level, this is the preseed type (will be used as
        a prefix in the template filenames).  Usually one of {'', 'enlist',
        'commissioning'}.
    :type prefix: basestring
    :param release: The Ubuntu release to be used.
    :type release: basestring
    :param default: Should we return the default ('generic') template as a
        last resort template?
    :type default: boolean

    Returns a list of possible preseed template filenames using the following
    lookup order:
    {prefix}_{node_architecture}_{node_subarchitecture}_{release}_{node_name}
    {prefix}_{node_architecture}_{node_subarchitecture}_{release}
    {prefix}_{node_architecture}
    {prefix}
    'generic'
    """
    arch = split_subarch(node.architecture)
    elements = []
    if prefix != '':
        elements.append(prefix)
    elements.extend(arch + [release, node.hostname])
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
    assert not isinstance(filenames, basestring)
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


class PreseedTemplate(tempita.Template):
    """A Tempita template specialised for preseed rendering."""


class TemplateNotFoundError(Exception):
    """The template has not been found."""

    def __init__(self, name):
        super(TemplateNotFoundError, self).__init__(name)
        self.name = name


# XXX: rvb 2012-06-18 bug=1013146:  'precise' is hardcoded here.
def load_preseed_template(node, prefix, release="precise"):
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


def get_maas_server_host():
    """Return MAAS' server name."""
    maas_url = Config.objects.get_config('maas_url')
    return urlparse(maas_url).netloc.split(':')[0]


# XXX: rvb 2012-06-19 bug=1013146:  'precise' is hardcoded here.
def get_preseed_context(node, release="precise"):
    """Return the context dictionary to be used to render preseed templates
    for this node.

    :param node: See `get_preseed_filenames`.
    :param prefix: See `get_preseed_filenames`.
    :param release: See `get_preseed_filenames`.
    :return: The context dictionary.
    :rtype: dict.
    """
    server_host = ''
    return {
        'node': node,
        'release': release,
        'server_host': server_host,
        'preseed_data': compose_preseed(node),
        'node_disable_pxe_url': '',  # TODO.
    }


# XXX: rvb 2012-06-19 bug=1013146:  'precise' is hardcoded here.
def render_preseed(node, prefix, release="precise"):
    """Find and load a `PreseedTemplate` for the given node.

    :param node: See `get_preseed_filenames`.
    :param prefix: See `get_preseed_filenames`.
    :param release: See `get_preseed_filenames`.
    :return: The rendered preseed string.
    :rtype: basestring.
    """
    template = load_preseed_template(node, prefix, release)
    context = get_preseed_context(node, release)
    return template.substitute(**context)
