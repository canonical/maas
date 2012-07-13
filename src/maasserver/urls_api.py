# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""URL API routing configuration."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from django.conf.urls.defaults import (
    patterns,
    url,
    )
from maasserver.api import (
    AccountHandler,
    AdminRestrictedResource,
    api_doc,
    FilesHandler,
    MAASHandler,
    NodeGroupHandler,
    NodeGroupsHandler,
    NodeHandler,
    NodeMacHandler,
    NodeMacsHandler,
    NodesHandler,
    pxeconfig,
    RestrictedResource,
    )
from maasserver.api_auth import api_auth


account_handler = RestrictedResource(AccountHandler, authentication=api_auth)
files_handler = RestrictedResource(FilesHandler, authentication=api_auth)
node_handler = RestrictedResource(NodeHandler, authentication=api_auth)
nodes_handler = RestrictedResource(NodesHandler, authentication=api_auth)
node_mac_handler = RestrictedResource(NodeMacHandler, authentication=api_auth)
node_macs_handler = RestrictedResource(
    NodeMacsHandler, authentication=api_auth)
nodegroup_handler = RestrictedResource(
    NodeGroupHandler, authentication=api_auth)
nodegroups_handler = RestrictedResource(
    NodeGroupsHandler, authentication=api_auth)


# Admin handlers.
maas_handler = AdminRestrictedResource(MAASHandler, authentication=api_auth)


# API URLs accessible to anonymous users.
urlpatterns = patterns('',
    url(r'doc/$', api_doc, name='api-doc'),
    url(r'pxeconfig/$', pxeconfig, name='pxeconfig'),
)


# API URLs for logged-in users.
urlpatterns += patterns('',
    url(
        r'nodes/(?P<system_id>[\w\-]+)/macs/(?P<mac_address>.+)/$',
        node_mac_handler, name='node_mac_handler'),
    url(
        r'nodes/(?P<system_id>[\w\-]+)/macs/$', node_macs_handler,
        name='node_macs_handler'),

    url(
        r'nodes/(?P<system_id>[\w\-]+)/$', node_handler,
        name='node_handler'),
    url(r'nodes/$', nodes_handler, name='nodes_handler'),
    url(
        r'nodegroups/(?P<name>[^/]+)/$',
        nodegroup_handler, name='nodegroup'),
    url(r'nodegroups/$', nodegroups_handler, name='nodegroups'),
    url(r'files/$', files_handler, name='files_handler'),
    url(r'account/$', account_handler, name='account_handler'),
)


# API URLs for admin users.
urlpatterns += patterns('',
    url(r'maas/$', maas_handler, name='maas_handler'),
)
