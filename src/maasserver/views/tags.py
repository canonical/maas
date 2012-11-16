# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tag views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'TagView',
    ]

from maasserver.models import Tag
from maasserver.views import PaginatedListView


class TagView(PaginatedListView):
    """Basic view of a tag.
    """

    template_name = 'maasserver/tag_view.html'
    context_object_name = 'node_list'

    def get(self, request, *args, **kwargs):
        self.tag = Tag.objects.get_tag_or_404(
            name=kwargs.get('name', None),
            user=self.request.user,
            to_edit=False)
        return super(TagView, self).get(request, *args, **kwargs)

    def get_queryset(self):
        nodes = Tag.objects.get_nodes(
            self.tag, user=self.request.user, prefetch_mac=True,
            ).order_by('-created')
        nodes = nodes.prefetch_related('nodegroup')
        nodes = nodes.prefetch_related('nodegroup__nodegroupinterface_set')
        return nodes

    def get_context_data(self, **kwargs):
        context = super(TagView, self).get_context_data(**kwargs)
        context['tag'] = self.tag
        return context
