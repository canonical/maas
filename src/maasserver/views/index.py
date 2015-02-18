# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Index view."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "IndexView",
    ]

from django.views.generic.base import TemplateView
from maasserver.eventloop import services


class IndexView(TemplateView):
    template_name = 'maasserver/index.html'

    def get_context_data(self, **kwargs):
        """Return context data that is passed into the template."""
        context = super(IndexView, self).get_context_data(**kwargs)
        try:
            port = services.getServiceNamed("web").endpoint.port
        except KeyError:
            port = None
        context['webapp_port'] = port
        return context
