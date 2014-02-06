# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Networks views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'NetworkAdd',
    'NetworkDelete',
    'NetworkEdit',
    'NetworkListView',
    'NetworkView',
    ]

from apiclient.utils import urlencode
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404
from django.views.generic import (
    CreateView,
    DetailView,
    UpdateView,
    )
from maasserver.models import Network
from maasserver.views import (
    HelpfulDeleteView,
    PaginatedListView,
    )


class NetworkListView(PaginatedListView):

    context_object_name = "network_list"

    def get_queryset(self):
        return Network.objects.all().order_by('name')


class NetworkView(DetailView):
    pass


class NetworkAdd(CreateView):
    pass


class NetworkEdit(UpdateView):
    pass


class NetworkDelete(HelpfulDeleteView):
    pass
