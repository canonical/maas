# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""URL routing configuration."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import re

from django.conf import settings as django_settings
from django.conf.urls.defaults import (
    include,
    patterns,
    url,
    )
from django.contrib.auth.decorators import user_passes_test
from django.views.generic.simple import (
    direct_to_template,
    redirect_to,
    )
from maasserver.models import Node
from maasserver.views.account import (
    login,
    logout,
    )
from maasserver.views.combo import combo_view
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
    settings_add_archive,
    )


def adminurl(regexp, view, *args, **kwargs):
    view = user_passes_test(lambda u: u.is_superuser)(view)
    return url(regexp, view, *args, **kwargs)


## URLs accessible to anonymous users.
urlpatterns = patterns('maasserver.views',
    url(
        r'^%s' % re.escape(django_settings.YUI_COMBO_URL), combo_view,
        name='yui-combo'),
    url(r'^accounts/login/$', login, name='login'),
    url(
        r'^robots\.txt$', direct_to_template,
        {'template': 'maasserver/robots.txt', 'mimetype': 'text/plain'},
        name='robots'),
    url(
        r'^favicon\.ico$', redirect_to, {'url': '/static/img/favicon.ico'},
        name='favicon'),
)

## URLs for logged-in users.
# Preferences views.
urlpatterns += patterns('maasserver.views',
    url(r'^account/prefs/$', userprefsview, name='prefs'),
    url(
        r'^account/prefs/sshkey/add/$', SSHKeyCreateView.as_view(),
        name='prefs-add-sshkey'),
    url(
        r'^account/prefs/sshkey/delete/(?P<keyid>\d*)/$',
        SSHKeyDeleteView.as_view(), name='prefs-delete-sshkey'),
    )

# Logout view.
urlpatterns += patterns('maasserver.views',
    url(r'^accounts/logout/$', logout, name='logout'),
)

# Nodes views.
urlpatterns += patterns('maasserver.views',
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
urlpatterns += patterns('maasserver.views',
    adminurl(r'^settings/$', settings, name='settings'),
    adminurl(
        r'^settings/archives/add/$', settings_add_archive,
        name='settings-add-archive'),
    adminurl(r'^accounts/add/$', AccountsAdd.as_view(), name='accounts-add'),
    adminurl(
        r'^accounts/(?P<username>\w+)/edit/$', AccountsEdit.as_view(),
        name='accounts-edit'),
    adminurl(
        r'^accounts/(?P<username>\w+)/view/$', AccountsView.as_view(),
        name='accounts-view'),
    adminurl(
        r'^accounts/(?P<username>\w+)/del/$', AccountsDelete.as_view(),
        name='accounts-del'),
)


# API URLs.
urlpatterns += patterns('',
    (r'^api/1\.0/', include('maasserver.urls_api'))
    )
