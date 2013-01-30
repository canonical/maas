# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'absolute_reverse',
    'build_absolute_uri',
    'find_nodegroup',
    'get_db_state',
    'ignore_unused',
    'is_local_cluster_UUID',
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
from maasserver.utils.orm import get_one


def get_db_state(instance, field_name):
    """Get the persisted state of a given field for a given model instance.

    :param instance: The model instance to consider.
    :type instance: :class:`django.db.models.Model`
    :param field_name: The name of the field to return.
    :type field_name: basestring
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


def is_local_cluster_UUID(uuid):
    """Return whether the given UUID is the UUID of the local cluster."""
    try:
        cluster_config = open(settings.LOCAL_CLUSTER_CONFIG).read()
        match = re.search(
            "CLUSTER_UUID=(?P<quote>[\"']?)([^\"']+)(?P=quote)",
            cluster_config)
        if match is not None:
            return uuid == match.groups()[1]
        else:
            return False
    except IOError as error:
        if error.errno == errno.ENOENT:
            # Cluster config file is not present.
            return False
        else:
            # Anything else is an error.
            raise


def find_nodegroup(request):
    """Find the nodegroup whose subnet contains the IP Address of the
    originating host of the request..

    The matching nodegroup may have multiple interfaces on the subnet,
    but there can be only one matching nodegroup.
    """
    # Circular imports.
    from maasserver.models import NodeGroup
    ip_address = request.META['REMOTE_ADDR']
    if ip_address is not None:
        management_statuses = (
            NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
        )
        query = NodeGroup.objects.raw("""
            SELECT *
            FROM maasserver_nodegroup
            WHERE id IN (
                SELECT nodegroup_id
                FROM maasserver_nodegroupinterface
                WHERE (inet %s & subnet_mask) = (ip & subnet_mask)
                AND management IN %s
            )
            """, [
                ip_address,
                management_statuses,
                ]
            )
        return get_one(query)
    return None
