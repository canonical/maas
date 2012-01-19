# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    print_function,
    unicode_literals,
    )

"""URL routing configuration."""

__metaclass__ = type
__all__ = []

from django.conf.urls.defaults import (
    patterns,
    url,
    )
from django.views.generic import ListView
from maasserver.api import (
    NodeHandler,
    NodeMacsHandler,
    )
from maasserver.models import Node
from maasserver.views import (
    NodesCreateView,
    NodeView,
    )
from piston.resource import Resource


urlpatterns = patterns('maasserver.views',
    url(r'^$', ListView.as_view(model=Node), name='index'),
    url(r'^nodes/create/$', NodesCreateView.as_view(), name='node-create'),
    url(r'^nodes/([\w\-]+)/$', NodeView.as_view(), name='node-view'),
)

# Api.
node_handler = Resource(NodeHandler)
node_macs_handler = Resource(NodeMacsHandler)

urlpatterns += patterns('maasserver.views',

    url(r'^api/nodes/([\w\-]+)/macs/(.+)/$', node_macs_handler),
    url(r'^api/nodes/([\w\-]+)/macs/$', node_macs_handler),

    url(r'^api/nodes/([\w\-]+)/$', node_handler),
    url(r'^api/nodes/$', node_handler),
)
