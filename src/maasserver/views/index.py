# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Index view."""

__all__ = [
    "IndexView",
    ]

from django.views.generic.base import TemplateView
from maasserver.config import IS_PREMIUM


class IndexView(TemplateView):
    template_name = 'maasserver/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_premium'] = IS_PREMIUM
        return context
