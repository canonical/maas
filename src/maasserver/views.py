# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Views."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "logout",
    "NodeView",
    "NodesCreateView",
    ]

from django.contrib.auth.views import logout as dj_logout
from django.shortcuts import get_object_or_404
from django.views.generic import (
    CreateView,
    ListView,
    )
from maasserver.models import Node


def logout(request):
    return dj_logout(request, next_page='/')


class NodeView(ListView):

    context_object_name = "node_list"

    def get_queryset(self):
        node = get_object_or_404(Node, name__iexact=self.args[0])
        return Node.get_visible_nodes.filter(node=node)


class NodesCreateView(CreateView):

    model = Node
    success_url = '/'
