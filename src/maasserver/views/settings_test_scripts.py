# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test Scripts Settings views."""

__all__ = [
    "TestScriptCreate",
    "TestScriptDelete",
    ]

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.views.generic import (
    CreateView,
    DeleteView,
)
from maasserver.forms.script import TestingScriptForm
from maasserver.utils.django_urls import reverse
from metadataserver.models import Script

# The anchor of the test scripts slot on the settings page.
TEST_SCRIPTS_ANCHOR = 'test_scripts'


class TestScriptDelete(DeleteView):

    template_name = (
        'maasserver/settings_confirm_delete_test_script.html')
    context_object_name = 'script_to_delete'

    def get_object(self):
        id = self.kwargs.get('id', None)
        return get_object_or_404(Script, id=id)

    def get_next_url(self):
        return reverse('settings') + '#' + TEST_SCRIPTS_ANCHOR

    def delete(self, request, *args, **kwargs):
        script = self.get_object()
        script.delete()
        messages.info(
            request, "Test script %s deleted." % script.name)
        return HttpResponseRedirect(self.get_next_url())


class TestScriptCreate(CreateView):
    template_name = 'maasserver/settings_add_test_script.html'
    form_class = TestingScriptForm
    context_object_name = 'testscript'

    def get_success_url(self):
        return reverse('settings') + '#' + TEST_SCRIPTS_ANCHOR

    def form_valid(self, form):
        messages.info(self.request, "Test script created.")
        return super(TestScriptCreate, self).form_valid(form)
