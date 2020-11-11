# Copyright 2012-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Views."""


from django.shortcuts import redirect
from django.views.generic import TemplateView


def handler404(request, *args, **kwargs):
    """404 Handler, just redirects to index.

    Index is handled by the static content loaded by the twisted WebApp.
    """
    return redirect("/MAAS/")


class TextTemplateView(TemplateView):
    """A text-based :class:`django.views.generic.TemplateView`."""

    def render_to_response(self, context, **response_kwargs):
        response_kwargs["content_type"] = "text/plain"
        return super(TemplateView, self).render_to_response(
            context, **response_kwargs
        )
