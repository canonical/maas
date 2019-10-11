# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Index view."""

__all__ = ["IndexView"]

from django.views.generic.base import TemplateView


class IndexView(TemplateView):
    template_name = "maasserver/index.html"
