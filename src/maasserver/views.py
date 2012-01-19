# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import print_function

"""Views."""

__metaclass__ = type
__all__ = [
    "NodeView",
    "NodesCreateView",
    ]

from django.shortcuts import get_object_or_404
from django.views.generic import (
    CreateView,
    ListView,
    )
from maasserver.models import Node


class NodeView(ListView):

    context_object_name = "node_list"

    def get_queryset(self):
        node = get_object_or_404(Node, name__iexact=self.args[0])
        return Node.objects.filter(node=node)


class NodesCreateView(CreateView):

    model = Node
#    template_name = 'maasserver/node_create.html'
    success_url = '/'
