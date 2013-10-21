# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'absolute_reverse',
    'build_absolute_uri',
    'find_nodegroup',
    'get_db_state',
    'get_local_cluster_UUID',
    'ignore_unused',
    'map_enum',
    'strip_domain',
    ]

import errno
import re
from urllib import urlencode
from urlparse import urljoin

from django.conf import settings
from django.core.urlresolvers import reverse
from maasserver.enum import NODEGROUPINTERFACE_MANAGEMENT
from maasserver.exceptions import NodeGroupMisconfiguration
from maasserver.utils.orm import get_one


def get_db_state(instance, field_name):
    """Get the persisted state of a given field for a given model instance.

    :param instance: The model instance to consider.
    :type instance: :class:`django.db.models.Model`
    :param field_name: The name of the field to return.
    :type field_name: unicode
    """
    obj = get_one(instance.__class__.objects.filter(pk=instance.pk))
    if obj is None:
        return None
    else:
        return getattr(obj, field_name)


def ignore_unused(*args):
    """Suppress warnings about unused variables.

    This function does nothing.  Use it whenever you have deliberately
    unused symbols: pass them to this function and lint checkers will no
    longer consider them unused.
    """


def map_enum(enum_class):
    """Map out an enumeration class as a "NAME: value" dict."""
    # Filter out anything that starts with '_', which covers private and
    # special methods.  We can make this smarter later if we start using
    # a smarter enumeration base class etc.  Or if we switch to a proper
    # enum mechanism, this function will act as a marker for pieces of
    # code that should be updated.
    return {
        key: value
        for key, value in vars(enum_class).items()
        if not key.startswith('_')
    }


def absolute_reverse(view_name, query=None, base_url=None, *args, **kwargs):
    """Return the absolute URL (i.e. including the URL scheme specifier and
    the network location of the MAAS server).  Internally this method simply
    calls Django's 'reverse' method and prefixes the result of that call with
    the configured DEFAULT_MAAS_URL.

    :param view_name: Django's view function name/reference or URL pattern
        name for which to compute the absolute URL.
    :param query: Optional query argument which will be passed down to
        urllib.urlencode.  The result of that call will be appended to the
        resulting url.
    :param base_url: Optional url used as base.  If None is provided, then
        settings.DEFAULT_MAAS_URL will be used.
    :param args: Positional arguments for Django's 'reverse' method.
    :param kwargs: Named arguments for Django's 'reverse' method.
    """
    if not base_url:
        base_url = settings.DEFAULT_MAAS_URL
    url = urljoin(base_url, reverse(view_name, *args, **kwargs))
    if query is not None:
        url += '?%s' % urlencode(query, doseq=True)
    return url


def build_absolute_uri(request, path):
    """Return absolute URI corresponding to given absolute path.

    :param request: An http request to the API.  This is needed in order to
        figure out how the client is used to addressing
        the API on the network.
    :param path: The absolute http path to a given resource.
    :return: Full, absolute URI to the resource, taking its networking
        portion from `request` but the rest from `path`.
    """
    scheme = "https" if request.is_secure() else "http"
    return "%s://%s%s" % (scheme, request.get_host(), path)


def strip_domain(hostname):
    """Return `hostname` with the domain part removed."""
    return hostname.split('.', 1)[0]


def get_local_cluster_UUID():
    """Return the UUID of the local cluster (or None if it cannot be found)."""
    try:
        cluster_config = open(settings.LOCAL_CLUSTER_CONFIG).read()
        match = re.search(
            "CLUSTER_UUID=(?P<quote>[\"']?)([^\"']+)(?P=quote)",
            cluster_config)
        if match is not None:
            return match.groups()[1]
        else:
            return None
    except IOError as error:
        if error.errno == errno.ENOENT:
            # Cluster config file is not present.
            return None
        else:
            # Anything else is an error.
            raise


def find_nodegroup(request):
    """Find the nodegroup whose subnet contains the requester's address.

    There may be multiple matching nodegroups, but this endeavours to choose
    the most appropriate.

    :raises `maasserver.exceptions.NodeGroupMisconfiguration`: When more than
        one nodegroup claims to manage the requester's network.
    """
    # Circular imports.
    from maasserver.models import NodeGroup
    ip_address = request.META['REMOTE_ADDR']
    if ip_address is None:
        return None
    else:
        # Fetch nodegroups with interfaces in the requester's network,
        # preferring those with managed networks first. The `NodeGroup`
        # objects returned are annotated with the `management` field of the
        # matching `NodeGroupInterface`. See https://docs.djangoproject.com
        # /en/dev/topics/db/sql/#adding-annotations for this curious feature
        # of Django's ORM.
        query = NodeGroup.objects.raw("""
            SELECT
              ng.*,
              ngi.management
            FROM
              maasserver_nodegroup AS ng,
              maasserver_nodegroupinterface AS ngi
            WHERE
              ng.id = ngi.nodegroup_id
             AND
              (inet %s & ngi.subnet_mask) = (ngi.ip & ngi.subnet_mask)
            ORDER BY
              ngi.management DESC,
              ng.id ASC
            """, [ip_address])
        nodegroups = list(query)
        if len(nodegroups) == 0:
            return None
        elif len(nodegroups) == 1:
            return nodegroups[0]
        else:
            # There are multiple matching nodegroups. Only zero or one may
            # have a managed interface, otherwise it is a misconfiguration.
            unmanaged = NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED
            nodegroups_with_managed_interfaces = {
                nodegroup.id for nodegroup in nodegroups
                if nodegroup.management != unmanaged
                }
            if len(nodegroups_with_managed_interfaces) > 1:
                raise NodeGroupMisconfiguration(
                    "Multiple clusters on the same network; only "
                    "one cluster may manage the network of which "
                    "%s is a member." % ip_address)
            return nodegroups[0]
