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
from django.views.generic import (
    UpdateView,
    )


class TagView(UpdateView):
    """Basic view of a tag.
    """

    template_name = 'maasserver/tag_view.html'
    context_object_name = 'tag'

    def get_object(self):
        name = self.kwargs.get('name', None)
        tag = Tag.objects.get_tag_or_404(
            name=name, user=self.request.user,
            to_edit=False)
        return tag

    def get_context_data(self, **kwargs):
        context = super(TagView, self).get_context_data(**kwargs)
        nodes = Tag.objects.get_nodes(context['tag'], self.request.user,
            prefetch_mac=True)
        context['node_list'] = nodes
        return context
