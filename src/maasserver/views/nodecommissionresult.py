# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Views for node commissioning results."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'NodeCommissionResultListView',
    ]

from django.shortcuts import get_object_or_404
from django.views.generic import DetailView
from maasserver.views import PaginatedListView
from metadataserver.models import NodeCommissionResult


class NodeCommissionResultListView(PaginatedListView):

    template_name = 'maasserver/nodecommissionresult-list.html'
    context_object_name = 'results_list'

    def get_queryset(self):
        results = NodeCommissionResult.objects.all()
        system_ids = self.request.GET.getlist('node')
        if system_ids is not None and len(system_ids) > 0:
            results = results.filter(node__system_id__in=system_ids)
        return results.order_by('node', '-created', 'name')


class NodeCommissionResultView(DetailView):

    template_name = 'metadataserver/nodecommissionresult.html'

    def get_object(self):
        result_id = self.kwargs.get('id')
        return get_object_or_404(NodeCommissionResult, id=result_id)
