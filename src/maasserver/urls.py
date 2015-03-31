# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""URL routing configuration."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


from django.conf.urls import (
    include,
    patterns,
    url,
)
from django.contrib.auth.decorators import user_passes_test
from maasserver.bootresources import (
    simplestreams_file_handler,
    simplestreams_stream_handler,
)
from maasserver.enum import NODEGROUP_STATUS
from maasserver.views import TextTemplateView
from maasserver.views.account import (
    login,
    logout,
)
from maasserver.views.clusters import (
    ClusterDelete,
    ClusterEdit,
    ClusterInterfaceCreate,
    ClusterInterfaceDelete,
    ClusterInterfaceEdit,
    ClusterListView,
)
from maasserver.views.images import (
    ImageDeleteView,
    ImagesView,
)
from maasserver.views.index import IndexView
from maasserver.views.networks import (
    NetworkAdd,
    NetworkDelete,
    NetworkEdit,
    NetworkListView,
    NetworkView,
)
from maasserver.views.prefs import (
    SSHKeyCreateView,
    SSHKeyDeleteView,
    SSLKeyCreateView,
    SSLKeyDeleteView,
    userprefsview,
)
from maasserver.views.rpc import info
from maasserver.views.settings import (
    AccountsAdd,
    AccountsDelete,
    AccountsEdit,
    AccountsView,
    settings,
)
from maasserver.views.settings_commissioning_scripts import (
    CommissioningScriptCreate,
    CommissioningScriptDelete,
)
from maasserver.views.settings_license_keys import (
    LicenseKeyCreate,
    LicenseKeyDelete,
    LicenseKeyEdit,
)
from maasserver.views.zones import (
    ZoneAdd,
    ZoneDelete,
    ZoneEdit,
    ZoneListView,
    ZoneView,
)


def adminurl(regexp, view, *args, **kwargs):
    view = user_passes_test(lambda u: u.is_superuser)(view)
    return url(regexp, view, *args, **kwargs)


# # URLs accessible to anonymous users.
# Combo URLs.
urlpatterns = patterns(
    '',
    (r'combo/', include('maasserver.urls_combo'))
)

# Anonymous views.
urlpatterns += patterns(
    'maasserver.views',
    url(r'^accounts/login/$', login, name='login'),
    url(
        r'^images-stream/streams/v1/(?P<filename>.*)$',
        simplestreams_stream_handler, name='simplestreams_stream_handler'),
    url(
        r'^images-stream/(?P<os>.*)/(?P<arch>.*)/(?P<subarch>.*)/'
        '(?P<series>.*)/(?P<version>.*)/(?P<filename>.*)$',
        simplestreams_file_handler, name='simplestreams_file_handler'),
    url(
        r'^robots\.txt$', TextTemplateView.as_view(
            template_name='maasserver/robots.txt'),
        name='robots'),
)

# # URLs for logged-in users.
# Preferences views.
urlpatterns += patterns(
    'maasserver.views',
    url(r'^account/prefs/$', userprefsview, name='prefs'),
    url(
        r'^account/prefs/sshkey/add/$', SSHKeyCreateView.as_view(),
        name='prefs-add-sshkey'),
    url(
        r'^account/prefs/sshkey/delete/(?P<keyid>\d*)/$',
        SSHKeyDeleteView.as_view(), name='prefs-delete-sshkey'),
    url(
        r'^account/prefs/sslkey/add/$', SSLKeyCreateView.as_view(),
        name='prefs-add-sslkey'),
    url(
        r'^account/prefs/sslkey/delete/(?P<keyid>\d*)/$',
        SSLKeyDeleteView.as_view(), name='prefs-delete-sslkey'),
    )
# Logout view.
urlpatterns += patterns(
    'maasserver.views',
    url(r'^accounts/logout/$', logout, name='logout'),
)


# Index view.
urlpatterns += patterns(
    'maasserver.views',
    url(
        r'^$',
        IndexView.as_view(),
        name='index'),
    )


# # URLs for admin users.
# Settings views.
urlpatterns += patterns(
    'maasserver.views',
    adminurl(
        r'^clusters/$',
        ClusterListView.as_view(status=NODEGROUP_STATUS.ACCEPTED),
        name='cluster-list'),
    adminurl(
        r'^clusters/pending/$',
        ClusterListView.as_view(status=NODEGROUP_STATUS.PENDING),
        name='cluster-list-pending'),
    adminurl(
        r'^clusters/rejected/$',
        ClusterListView.as_view(status=NODEGROUP_STATUS.REJECTED),
        name='cluster-list-rejected'),
    adminurl(
        r'^clusters/(?P<uuid>[\w\-]+)/edit/$', ClusterEdit.as_view(),
        name='cluster-edit'),
    adminurl(
        r'^clusters/(?P<uuid>[\w\-]+)/delete/$', ClusterDelete.as_view(),
        name='cluster-delete'),
    adminurl(
        r'^clusters/(?P<uuid>[\w\-]+)/interfaces/add/$',
        ClusterInterfaceCreate.as_view(), name='cluster-interface-create'),
    adminurl(
        r'^clusters/(?P<uuid>[\w\-]+)/interfaces/(?P<name>[^/]*)/'
        'edit/$',
        ClusterInterfaceEdit.as_view(), name='cluster-interface-edit'),
    adminurl(
        r'^clusters/(?P<uuid>[\w\-]+)/interfaces/(?P<name>[^/]*)/'
        'delete/$',
        ClusterInterfaceDelete.as_view(), name='cluster-interface-delete'),
    # XXX: rvb 2012-10-08 bug=1063881:
    # These two urls are only here to cope with the fact that an interface
    # can have an empty name, thus leading to urls containing the
    # pattern '//' that is then reduced by apache into '/'.
    adminurl(
        r'^clusters/(?P<uuid>[\w\-]+)/interfaces/(?P<name>)'
        'edit/$', ClusterInterfaceEdit.as_view()),
    adminurl(
        r'^clusters/(?P<uuid>[\w\-]+)/interfaces/(?P<name>)'
        'delete/$', ClusterInterfaceDelete.as_view()),
    # /XXX
    adminurl(r'^settings/$', settings, name='settings'),
    adminurl(r'^accounts/add/$', AccountsAdd.as_view(), name='accounts-add'),
    adminurl(
        r'^accounts/(?P<username>[^/]+)/edit/$', AccountsEdit.as_view(),
        name='accounts-edit'),
    adminurl(
        r'^accounts/(?P<username>[^/]+)/view/$', AccountsView.as_view(),
        name='accounts-view'),
    adminurl(
        r'^accounts/(?P<username>[^/]+)/del/$', AccountsDelete.as_view(),
        name='accounts-del'),
    adminurl(
        r'^commissioning-scripts/(?P<id>[\w\-]+)/delete/$',
        CommissioningScriptDelete.as_view(),
        name='commissioning-script-delete'),
    adminurl(
        r'^commissioning-scripts/add/$',
        CommissioningScriptCreate.as_view(),
        name='commissioning-script-add'),
    adminurl(
        r'^license-key/(?P<osystem>[^/]+)/(?P<distro_series>[^/]+)/delete/$',
        LicenseKeyDelete.as_view(),
        name='license-key-delete'),
    adminurl(
        r'^license-key/(?P<osystem>[^/]+)/(?P<distro_series>[^/]+)/edit/$',
        LicenseKeyEdit.as_view(),
        name='license-key-edit'),
    adminurl(
        r'^license-key/add/$',
        LicenseKeyCreate.as_view(),
        name='license-key-add'),
)

# Image views.
urlpatterns += patterns(
    'maasserver.views',
    url(r'^images/$', ImagesView.as_view(), name='images'),
    url(
        r'^images/(?P<resource_id>[\w\-]+)/delete/$',
        ImageDeleteView.as_view(), name='image-delete'),
)

# Zone views.
urlpatterns += patterns(
    'maasserver.views',
    url(r'^zones/$', ZoneListView.as_view(), name='zone-list'),
    url(
        r'^zones/(?P<name>[\w\-]+)/view/$', ZoneView.as_view(),
        name='zone-view'),
    adminurl(
        r'^zones/(?P<name>[\w\-]+)/edit/$', ZoneEdit.as_view(),
        name='zone-edit'),
    adminurl(
        r'^zones/(?P<name>[\w\-]+)/delete/$', ZoneDelete.as_view(),
        name='zone-del'),
    adminurl(r'^zones/add/$', ZoneAdd.as_view(), name='zone-add'),
)

# Network views.
urlpatterns += patterns(
    'maasserver.views',
    url(r'^networks/$', NetworkListView.as_view(), name='network-list'),
    url(
        r'^networks/(?P<name>[\w\-]+)/view/$', NetworkView.as_view(),
        name='network-view'),
    adminurl(
        r'^networks/(?P<name>[\w\-]+)/edit/$', NetworkEdit.as_view(),
        name='network-edit'),
    adminurl(
        r'^networks/(?P<name>[\w\-]+)/delete/$', NetworkDelete.as_view(),
        name='network-del'),
    adminurl(r'^networks/add/$', NetworkAdd.as_view(), name='network-add'),
)

# API URLs.
urlpatterns += patterns(
    '',
    (r'^api/1\.0/', include('maasserver.urls_api'))
    )

# RPC URLs.
urlpatterns += patterns(
    'maasserver.views.rpc',
    url(r'^rpc/$', info, name="rpc-info"),
)
