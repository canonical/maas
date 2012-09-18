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
    BootImagesHandler,
    describe,
    FilesHandler,
    MAASHandler,
    NodeGroupHandler,
    NodeGroupInterfaceHandler,
    NodeGroupInterfacesHandler,
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
boot_images_handler = RestrictedResource(
    BootImagesHandler, authentication=api_auth)


# Admin handlers.
maas_handler = AdminRestrictedResource(MAASHandler, authentication=api_auth)
nodegroupinterface_handler = AdminRestrictedResource(
    NodeGroupInterfaceHandler, authentication=api_auth)
nodegroupinterfaces_handler = AdminRestrictedResource(
    NodeGroupInterfacesHandler, authentication=api_auth)

# API URLs accessible to anonymous users.
urlpatterns = patterns('',
    url(r'doc/$', api_doc, name='api-doc'),
    url(r'describe/$', describe, name='describe'),
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
        r'nodegroups/(?P<uuid>[^/]+)/$',
        nodegroup_handler, name='nodegroup_handler'),
    url(r'nodegroups/$', nodegroups_handler, name='nodegroups_handler'),
    url(r'nodegroups/(?P<uuid>[^/]+)/interfaces/$',
        nodegroupinterfaces_handler, name='nodegroupinterfaces_handler'),
    url(r'nodegroups/(?P<uuid>[^/]+)/interfaces/(?P<interface>[^/]+)/$',
        nodegroupinterface_handler, name='nodegroupinterface_handler'),
    url(r'files/$', files_handler, name='files_handler'),
    url(r'account/$', account_handler, name='account_handler'),
    url(r'boot-images/$', boot_images_handler, name='boot_images_handler'),
)


# API URLs for admin users.
urlpatterns += patterns('',
    url(r'maas/$', maas_handler, name='maas_handler'),
)
