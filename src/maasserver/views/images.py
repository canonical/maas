# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Image views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "ImagesView",
    ]


from django.core.urlresolvers import reverse
from django.http import (
    HttpResponseForbidden,
    HttpResponseRedirect,
    )
from django.views.generic.base import TemplateView
from django.views.generic.edit import (
    FormMixin,
    ProcessFormView,
    )
from maasserver.bootresources import import_resources
from maasserver.enum import BOOT_RESOURCE_TYPE
from maasserver.models import BootResource


class ImagesView(TemplateView, FormMixin, ProcessFormView):
    template_name = 'maasserver/images.html'
    context_object_name = "images"
    status = None

    def get_context_data(self, **kwargs):
        """Return context data that is passed into the template."""
        context = super(ImagesView, self).get_context_data(**kwargs)
        context['ubuntu_resources'] = self.get_ubuntu_resources()
        return context

    def post(self, request, *args, **kwargs):
        """Handle a POST request."""
        # Only administrators can change options on this page.
        if not self.request.user.is_superuser:
            return HttpResponseForbidden()
        if 'ubuntu_images' in request.POST:
            import_resources()
            return HttpResponseRedirect(reverse('images'))
        else:
            # Unknown action: redirect to the images page (this
            # shouldn't happen).
            return HttpResponseRedirect(reverse('images'))

    def get_ubuntu_resources(self):
        """Return all Ubuntu resources, for usage in the template."""
        return BootResource.objects.filter(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name__startswith='ubuntu/')
