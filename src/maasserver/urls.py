
from django.conf.urls.defaults import *
from django.views.generic import ListView
from piston.resource import Resource
from maasserver.models import Node
from maasserver.views import NodeView, NodesCreateView
from maasserver.api import NodeHandler, NodeMacsHandler


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

