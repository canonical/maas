# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""License Key Settings views."""

__all__ = ["LicenseKeyCreate", "LicenseKeyDelete", "LicenseKeyEdit"]

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.views.generic import CreateView, DeleteView, UpdateView
from maasserver.forms import LicenseKeyForm
from maasserver.models import LicenseKey
from maasserver.utils.django_urls import reverse

# The anchor of the license keys slot on the settings page.
LICENSE_KEY_ANCHOR = "license_keys"


class LicenseKeyDelete(DeleteView):

    template_name = "maasserver/settings_confirm_delete_license_key.html"
    context_object_name = "license_key_to_delete"

    def get_object(self):
        osystem = self.kwargs.get("osystem", None)
        distro_series = self.kwargs.get("distro_series", None)
        return get_object_or_404(
            LicenseKey, osystem=osystem, distro_series=distro_series
        )

    def get_next_url(self):
        return reverse("settings_license_keys") + "#" + LICENSE_KEY_ANCHOR

    def delete(self, request, *args, **kwargs):
        license_key = self.get_object()
        license_key.delete()
        messages.info(
            request,
            "License key %s/%s deleted."
            % (license_key.osystem, license_key.distro_series),
        )
        return HttpResponseRedirect(self.get_next_url())


class LicenseKeyCreate(CreateView):
    template_name = "maasserver/settings_add_license_key.html"
    form_class = LicenseKeyForm
    context_object_name = "licensekey"

    def get_success_url(self):
        return reverse("settings_license_keys") + "#" + LICENSE_KEY_ANCHOR

    def form_valid(self, form):
        messages.info(self.request, "License key created.")
        return super(LicenseKeyCreate, self).form_valid(form)


class LicenseKeyEdit(UpdateView):
    """View for editing a license key."""

    model = LicenseKey
    form_class = LicenseKeyForm
    template_name = "maasserver/settings_edit_license_key.html"

    def get_object(self):
        osystem = self.kwargs.get("osystem", None)
        distro_series = self.kwargs.get("distro_series", None)
        return get_object_or_404(
            LicenseKey, osystem=osystem, distro_series=distro_series
        )

    def get_success_url(self):
        return reverse("settings_license_keys") + "#" + LICENSE_KEY_ANCHOR

    def form_valid(self, form):
        messages.info(self.request, "License key updated.")
        return super(LicenseKeyEdit, self).form_valid(form)
