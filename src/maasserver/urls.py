# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""URL routing configuration."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from django.conf.urls.defaults import (
    patterns,
    url,
    )
from django.contrib.auth.views import login
from django.views.generic import ListView
from maasserver.api import (
    api_doc,
    NodeHandler,
    NodesHandler,
    NodeMacHandler,
    NodeMacsHandler,
    )
from maasserver.models import Node
from maasserver.views import (
    logout,
    NodesCreateView,
    NodeView,
    )
from piston.resource import Resource


# Urls accessible to anonymous users.
urlpatterns = patterns('maasserver.views',
    url(r'^accounts/login/$', login, name='login'),
    url(r'^accounts/logout/$', logout, name='logout'),
)

# Urls for logged-in users.
urlpatterns += patterns('maasserver.views',
    url(
        r'^$',
        ListView.as_view(model=Node, template_name="maasserver/index.html"),
        name='index'),
    url(r'^nodes/$', ListView.as_view(model=Node), name='node-list'),
    url(
        r'^nodes/create/$', NodesCreateView.as_view(), name='node-create'),
    url(r'^nodes/([\w\-]+)/$', NodeView.as_view(), name='node-view'),
)

# API.
node_handler = Resource(NodeHandler)
nodes_handler = Resource(NodesHandler)
node_mac_handler = Resource(NodeMacHandler)
node_macs_handler = Resource(NodeMacsHandler)

# API urls accessible to anonymous users.
urlpatterns += patterns('maasserver.views',
    url(r'^api/doc/$', api_doc, name='api-doc'),
)

# API urls for logged-in users.
urlpatterns += patterns('maasserver.views',
    url(
        r'^api/nodes/(?P<system_id>[\w\-]+)/macs/(?P<mac_address>.+)/$',
        node_mac_handler, name='node_mac_handler'),
    url(
        r'^api/nodes/(?P<system_id>[\w\-]+)/macs/$', node_macs_handler,
        name='node_macs_handler'),

    url(
        r'^api/nodes/(?P<system_id>[\w\-]+)/$', node_handler,
        name='node_handler'),
    url(r'^api/nodes/$', nodes_handler, name='nodes_handler'),
)
