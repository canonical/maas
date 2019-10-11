# Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test Scripts Settings views."""

__all__ = ["TestScriptCreate", "TestScriptDelete"]

from django.contrib import messages
from django.http import HttpResponseNotFound, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.views.generic import CreateView, DeleteView
from maasserver.audit import create_audit_event
from maasserver.enum import ENDPOINT
from maasserver.forms.script import TestingScriptForm
from maasserver.utils.django_urls import reverse
from metadataserver.models import Script
from provisioningserver.events import EVENT_TYPES

# The anchor of the test scripts slot on the settings page.
TEST_SCRIPTS_ANCHOR = "test_scripts"


class TestScriptDelete(DeleteView):

    template_name = "maasserver/settings_confirm_delete_test_script.html"
    context_object_name = "script_to_delete"

    def get_object(self):
        id = self.kwargs.get("id", None)
        return get_object_or_404(Script, id=id)

    def get_next_url(self):
        return reverse("settings_scripts") + "#" + TEST_SCRIPTS_ANCHOR

    def delete(self, request, *args, **kwargs):
        script = self.get_object()
        script.delete()
        create_audit_event(
            EVENT_TYPES.SETTINGS,
            ENDPOINT.UI,
            request,
            None,
            description=("Deleted script '%s'." % script.name),
        )
        messages.info(request, "Test script %s deleted." % script.name)
        return HttpResponseRedirect(self.get_next_url())


class TestScriptCreate(CreateView):
    template_name = "maasserver/settings_add_test_script.html"
    form_class = TestingScriptForm
    context_object_name = "testscript"

    def get_success_url(self):
        return reverse("settings_scripts") + "#" + TEST_SCRIPTS_ANCHOR

    def form_valid(self, form):
        if form.is_valid():
            form.save(self.request)
            messages.info(self.request, "Test script created.")
            return HttpResponseRedirect(self.get_success_url())
        return HttpResponseNotFound()
