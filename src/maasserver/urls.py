# Copyright 2012 Canonical Ltd.  This software is licensed under the
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
from maasserver.models import (
    Node,
    Zone,
    )
from maasserver.views import TextTemplateView
from maasserver.views.account import (
    login,
    logout,
    )
from maasserver.views.nodes import (
    enlist_preseed_view,
    MacAdd,
    MacDelete,
    NodeDelete,
    NodeEdit,
    NodeListView,
    NodePreseedView,
    NodeView,
    )
from maasserver.views.prefs import (
    SSHKeyCreateView,
    SSHKeyDeleteView,
    userprefsview,
    )
from maasserver.views.settings import (
    AccountsAdd,
    AccountsDelete,
    AccountsEdit,
    AccountsView,
    settings,
    )
from maasserver.views.settings_clusters import (
    ClusterDelete,
    ClusterEdit,
    ClusterInterfaceCreate,
    ClusterInterfaceDelete,
    ClusterInterfaceEdit,
    )
from maasserver.views.settings_commissioning_scripts import (
    CommissioningScriptCreate,
    CommissioningScriptDelete,
    )
from maasserver.views.tags import TagView
from maasserver.views.zones import (
    ZoneListView,
    ZoneView,
    )


def adminurl(regexp, view, *args, **kwargs):
    view = user_passes_test(lambda u: u.is_superuser)(view)
    return url(regexp, view, *args, **kwargs)


## URLs accessible to anonymous users.
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
        r'^robots\.txt$', TextTemplateView.as_view(
            template_name='maasserver/robots.txt'),
        name='robots'),
)

## URLs for logged-in users.
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
    )

# Logout view.
urlpatterns += patterns(
    'maasserver.views',
    url(r'^accounts/logout/$', logout, name='logout'),
)

# Nodes views.
urlpatterns += patterns(
    'maasserver.views',
    url(
        r'^$',
        NodeListView.as_view(template_name="maasserver/index.html"),
        name='index'),
    url(r'^nodes/$', NodeListView.as_view(model=Node), name='node-list'),
    url(r'^nodes/enlist-preseed/$', enlist_preseed_view,
        name='enlist-preseed-view'),
    url(
        r'^nodes/(?P<system_id>[\w\-]+)/view/$', NodeView.as_view(),
        name='node-view'),
    url(
        r'^nodes/(?P<system_id>[\w\-]+)/preseedview/$',
        NodePreseedView.as_view(), name='node-preseed-view'),
    url(
        r'^nodes/(?P<system_id>[\w\-]+)/edit/$', NodeEdit.as_view(),
        name='node-edit'),
    url(
        r'^nodes/(?P<system_id>[\w\-]+)/delete/$', NodeDelete.as_view(),
        name='node-delete'),
    url(
        r'^nodes/(?P<system_id>[\w\-]+)/macs/(?P<mac_address>.+)/delete/$',
        MacDelete.as_view(), name='mac-delete'),
    url(
        r'^nodes/(?P<system_id>[\w\-]+)/macs/add/$',
        MacAdd.as_view(), name='mac-add'),
)


## URLs for admin users.
# Settings views.
urlpatterns += patterns(
    'maasserver.views',
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
        r'^clusters/(?P<uuid>[\w\-]+)/interfaces/(?P<interface>[^/]*)/'
        'edit/$',
        ClusterInterfaceEdit.as_view(), name='cluster-interface-edit'),
    adminurl(
        r'^clusters/(?P<uuid>[\w\-]+)/interfaces/(?P<interface>[^/]*)/'
        'delete/$',
        ClusterInterfaceDelete.as_view(), name='cluster-interface-delete'),
    # XXX: rvb 2012-10-08 bug=1063881:
    # These two urls are only here to cope with the fact that an interface
    # can have an empty name, thus leading to urls containing the
    # pattern '//' that is then reduced by apache into '/'.
    adminurl(
        r'^clusters/(?P<uuid>[\w\-]+)/interfaces/(?P<interface>)'
        'edit/$', ClusterInterfaceEdit.as_view()),
    adminurl(
        r'^clusters/(?P<uuid>[\w\-]+)/interfaces/(?P<interface>)'
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
)

# Tag views.
urlpatterns += patterns(
    'maasserver.views',
    url(r'^tags/(?P<name>[\w\-]+)/view/$', TagView.as_view(), name='tag-view'),
)

# Zone views.
urlpatterns += patterns(
    'maasserver.views',
    url(
        r'^zones/$', ZoneListView.as_view(model=Zone), name='zone-list'),
    url(
        r'^zones/(?P<name>[\w\-]+)/view/$', ZoneView.as_view(model=Zone),
        name='zone-view'),
    adminurl(
        r'^zones/(?P<name>[\w\-]+)/edit/$', ZoneListView.as_view(model=Zone),
        # TODO: fix me with ZoneEdit.as_view(),
        name='zone-edit'),
    adminurl(
        r'^zones/(?P<name>[\w\-]+)/delete/$', ZoneListView.as_view(model=Zone),
        # TODO: fix me with ZoneDelete.as_view(),
        name='zone-del'),
    adminurl(
        r'^zones/add/$', ZoneListView.as_view(model=Zone),
        # TODO: fix me with ZoneAdd.as_view(),
        name='zone-add'),
)


# API URLs.
urlpatterns += patterns(
    '',
    (r'^api/1\.0/', include('maasserver.urls_api'))
    )
