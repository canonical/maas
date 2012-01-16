
from django.conf.urls.defaults import *
from django.views.generic import ListView
from maasserver.models import Node
from maasserver.views import NodeView, NodesCreateView

urlpatterns = patterns('maasserver.views',
    url(r'^$', ListView.as_view(model=Node), name='index'),
    url(r'^nodes/create/$', NodesCreateView.as_view(), name='node-create'),
    url(r'^nodes/(\w+)/$', NodeView.as_view(), name='node-view'),
)
