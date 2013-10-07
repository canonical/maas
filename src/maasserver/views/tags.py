# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tag views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'TagView',
    ]

from maasserver.enum import NODE_PERMISSION
from maasserver.models import (
    Node,
    Tag,
    )
from maasserver.views import PaginatedListView
from maasserver.views.nodes import prefetch_nodes_listing


class TagView(PaginatedListView):
    """Basic view of a tag.  Lists matching nodes."""

    template_name = 'maasserver/tag_view.html'
    context_object_name = 'node_list'

    def get(self, request, *args, **kwargs):
        self.tag = Tag.objects.get_tag_or_404(
            name=kwargs.get('name', None),
            user=self.request.user,
            to_edit=False)
        return super(TagView, self).get(request, *args, **kwargs)

    def get_queryset(self):
        nodes = Node.objects.get_nodes(
            user=self.request.user, perm=NODE_PERMISSION.VIEW,
            from_nodes=self.tag.node_set.all())
        nodes = nodes.order_by('-created')
        return prefetch_nodes_listing(nodes)

    def get_context_data(self, **kwargs):
        context = super(TagView, self).get_context_data(**kwargs)
        context['tag'] = self.tag
        return context
