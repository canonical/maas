# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Commissioning Scripts Settings views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "CommissioningScriptCreate",
    "CommissioningScriptDelete",
    ]

from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.views.generic import (
    CreateView,
    DeleteView,
    )
from maasserver.forms import CommissioningScriptForm
from metadataserver.models import CommissioningScript

# The anchor of the commissioning scripts slot on the settings page.
COMMISSIONING_SCRIPTS_ANCHOR = 'commissioning_scripts'


class CommissioningScriptDelete(DeleteView):

    template_name = (
        'maasserver/settings_confirm_delete_commissioning_script.html')
    context_object_name = 'script_to_delete'

    def get_object(self):
        id = self.kwargs.get('id', None)
        return get_object_or_404(CommissioningScript, id=id)

    def get_next_url(self):
        return reverse('settings') + '#' + COMMISSIONING_SCRIPTS_ANCHOR

    def delete(self, request, *args, **kwargs):
        script = self.get_object()
        script.delete()
        messages.info(
            request, "Commissioning script %s deleted." % script.name)
        return HttpResponseRedirect(self.get_next_url())


class CommissioningScriptCreate(CreateView):
    template_name = 'maasserver/settings_add_commissioning_script.html'
    form_class = CommissioningScriptForm
    context_object_name = 'commissioningscript'

    def get_success_url(self):
        return reverse('settings') + '#' + COMMISSIONING_SCRIPTS_ANCHOR

    def form_valid(self, form):
        messages.info(self.request, "Commissioning script created.")
        return super(CommissioningScriptCreate, self).form_valid(form)
