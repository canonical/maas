# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""URL API routing configuration."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from django.conf.urls import (
    patterns,
    url,
    )
from maasserver.api import (
    AccountHandler,
    api_doc,
    BootImagesHandler,
    CommissioningResultsHandler,
    CommissioningScriptHandler,
    CommissioningScriptsHandler,
    describe,
    FileHandler,
    FilesHandler,
    MaasHandler,
    NodeGroupHandler,
    NodeGroupInterfaceHandler,
    NodeGroupInterfacesHandler,
    NodeGroupsHandler,
    NodeHandler,
    NodeMacHandler,
    NodeMacsHandler,
    NodesHandler,
    pxeconfig,
    SSHKeyHandler,
    SSHKeysHandler,
    TagHandler,
    TagsHandler,
    UserHandler,
    UsersHandler,
    )
from maasserver.api_auth import api_auth
from maasserver.api_support import (
    AdminRestrictedResource,
    RestrictedResource,
    )


account_handler = RestrictedResource(AccountHandler, authentication=api_auth)
files_handler = RestrictedResource(FilesHandler, authentication=api_auth)
file_handler = RestrictedResource(FileHandler, authentication=api_auth)
node_handler = RestrictedResource(NodeHandler, authentication=api_auth)
nodes_handler = RestrictedResource(NodesHandler, authentication=api_auth)
node_mac_handler = RestrictedResource(NodeMacHandler, authentication=api_auth)
node_macs_handler = RestrictedResource(
    NodeMacsHandler, authentication=api_auth)
nodegroup_handler = RestrictedResource(
    NodeGroupHandler, authentication=api_auth)
nodegroups_handler = RestrictedResource(
    NodeGroupsHandler, authentication=api_auth)
nodegroupinterface_handler = RestrictedResource(
    NodeGroupInterfaceHandler, authentication=api_auth)
nodegroupinterfaces_handler = RestrictedResource(
    NodeGroupInterfacesHandler, authentication=api_auth)
boot_images_handler = RestrictedResource(
    BootImagesHandler, authentication=api_auth)
tag_handler = RestrictedResource(TagHandler, authentication=api_auth)
tags_handler = RestrictedResource(TagsHandler, authentication=api_auth)
commissioning_results_handler = RestrictedResource(
    CommissioningResultsHandler, authentication=api_auth)
sshkey_handler = RestrictedResource(SSHKeyHandler, authentication=api_auth)
sshkeys_handler = RestrictedResource(SSHKeysHandler, authentication=api_auth)
user_handler = RestrictedResource(UserHandler, authentication=api_auth)
users_handler = RestrictedResource(UsersHandler, authentication=api_auth)


# Admin handlers.
maas_handler = AdminRestrictedResource(MaasHandler, authentication=api_auth)
commissioning_script_handler = AdminRestrictedResource(
    CommissioningScriptHandler, authentication=api_auth)
commissioning_scripts_handler = AdminRestrictedResource(
    CommissioningScriptsHandler, authentication=api_auth)


# API URLs accessible to anonymous users.
urlpatterns = patterns(
    '',
    url(r'doc/$', api_doc, name='api-doc'),
    url(r'describe/$', describe, name='describe'),
    url(r'pxeconfig/$', pxeconfig, name='pxeconfig'),
)


# API URLs for logged-in users.
urlpatterns += patterns(
    '',
    url(
        r'^nodes/(?P<system_id>[\w\-]+)/macs/(?P<mac_address>.+)/$',
        node_mac_handler, name='node_mac_handler'),
    url(
        r'^nodes/(?P<system_id>[\w\-]+)/macs/$', node_macs_handler,
        name='node_macs_handler'),

    url(
        r'^nodes/(?P<system_id>[\w\-]+)/$', node_handler,
        name='node_handler'),
    url(r'^nodes/$', nodes_handler, name='nodes_handler'),
    # For backward compatibility, handle obviously repeated paths as if they
    # were not repeated. See https://bugs.launchpad.net/maas/+bug/1131323.
    url(r'^nodes/.*/nodes/$', nodes_handler),
    url(
        r'^nodegroups/(?P<uuid>[^/]+)/$',
        nodegroup_handler, name='nodegroup_handler'),
    url(r'^nodegroups/$', nodegroups_handler, name='nodegroups_handler'),
    url(r'^nodegroups/(?P<uuid>[^/]+)/interfaces/$',
        nodegroupinterfaces_handler, name='nodegroupinterfaces_handler'),
    url(r'^nodegroups/(?P<uuid>[^/]+)/interfaces/(?P<interface>[^/]+)/$',
        nodegroupinterface_handler, name='nodegroupinterface_handler'),
    url(r'^files/$', files_handler, name='files_handler'),
    url(r'^files/(?P<filename>.+)/$', file_handler, name='file_handler'),
    url(r'^account/$', account_handler, name='account_handler'),
    url(
        r'^account/prefs/sshkeys/(?P<keyid>[^/]+)/$', sshkey_handler,
        name='sshkey_handler'),
    url(r'^account/prefs/sshkeys/$', sshkeys_handler, name='sshkeys_handler'),
    url(r'^boot-images/$', boot_images_handler, name='boot_images_handler'),
    url(r'^tags/(?P<name>[\w\-]+)/$', tag_handler, name='tag_handler'),
    url(r'^tags/$', tags_handler, name='tags_handler'),
    url(
        r'^commissioning-results/$',
        commissioning_results_handler, name='commissioning_results_handler'),
    url(r'^users/$', users_handler, name='users_handler'),
    url(r'^users/(?P<username>[^/]+)/$', user_handler, name='user_handler'),
)


# API URLs for admin users.
urlpatterns += patterns(
    '',
    url(r'^maas/$', maas_handler, name='maas_handler'),
    url(
        r'^commissioning-scripts/$', commissioning_scripts_handler,
        name='commissioning_scripts_handler'),
    url(
        r'^commissioning-scripts/(?P<name>[^/]+)$',
        commissioning_script_handler, name='commissioning_script_handler'),
)
