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
    "NodeListView",
    "NodesCreateView",
    ]

from django.contrib import messages
from django.contrib.auth.views import logout as dj_logout
from django.core.urlresolvers import reverse
from django.views.generic import (
    CreateView,
    ListView,
    )
from maasserver.models import Node


def logout(request):
    messages.info(request, 'You have been logged out.')
    return dj_logout(request, next_page=reverse('login'))


class NodeListView(ListView):

    context_object_name = "node_list"

    def get_queryset(self):
        return Node.objects.get_visible_nodes(user=self.request.user)


class NodesCreateView(CreateView):

    model = Node

    def get_success_url(self):
        return reverse('index')
