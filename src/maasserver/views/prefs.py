# Copyright 2012-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Preferences views."""

__all__ = ["userprefsview"]

from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import PermissionDenied
from django.http import (
    HttpResponseNotAllowed,
    HttpResponseNotFound,
    HttpResponseRedirect,
)
from django.shortcuts import get_object_or_404, render
from django.views.generic import CreateView
from maasserver.audit import create_audit_event
from maasserver.enum import ENDPOINT
from maasserver.forms import ProfileForm, SSLKeyForm
from maasserver.models import SSLKey
from maasserver.utils.django_urls import reverse
from maasserver.views import HelpfulDeleteView, process_form
from provisioningserver.events import EVENT_TYPES


class SSLKeyCreateView(CreateView):

    form_class = SSLKeyForm
    template_name = "maasserver/prefs_add_sslkey.html"

    def get_form_kwargs(self):
        kwargs = super(SSLKeyCreateView, self).get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        if form.is_valid():
            form.save(ENDPOINT.UI, self.request)
            messages.info(self.request, "SSL key added.")
            return HttpResponseRedirect(self.get_success_url())
        return HttpResponseNotFound()

    def get_success_url(self):
        return reverse("prefs")


class SSLKeyDeleteView(HelpfulDeleteView):

    template_name = "maasserver/prefs_confirm_delete_sslkey.html"
    context_object_name = "sslkey"
    model = SSLKey

    def get_object(self):
        keyid = self.kwargs.get("keyid", None)
        key = get_object_or_404(SSLKey, id=keyid)
        if key.user != self.request.user:
            raise PermissionDenied("Can't delete this key.  It's not yours.")
        create_audit_event(
            EVENT_TYPES.AUTHORISATION,
            ENDPOINT.UI,
            self.request,
            None,
            description="Deleted SSL key id='%s'." % keyid,
        )
        return key

    def get_next_url(self):
        return reverse("prefs")


def userprefsview(request):
    have_external_auth = bool(request.external_auth_info)
    if have_external_auth and request.method == "POST":
        return HttpResponseNotAllowed(["GET"])

    user = request.user
    # Process the profile update form.
    profile_form, response = process_form(
        request,
        ProfileForm,
        reverse("prefs"),
        "profile",
        "Profile updated.",
        {"instance": user},
    )
    if response is not None:
        return response
    if have_external_auth:
        for field in profile_form:
            field.field.disabled = True

    # Process the password change form.
    password_form, response = process_form(
        request,
        PasswordChangeForm,
        reverse("prefs"),
        "password",
        "Password updated.",
        {"user": user},
    )
    password_form.fields["old_password"].widget.attrs.pop("autofocus", None)
    if response is not None:
        create_audit_event(
            EVENT_TYPES.AUTHORISATION,
            ENDPOINT.UI,
            request,
            None,
            description="Updated password.",
        )
        return response

    return render(
        request,
        "maasserver/prefs.html",
        {"profile_form": profile_form, "password_form": password_form},
    )
