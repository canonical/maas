# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Account views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "login",
    "logout",
    ]

from django import forms
from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth.views import (
    login as dj_login,
    logout as dj_logout,
)
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from maasserver.models import UserProfile


def login(request):
    extra_context = {
        'no_users': UserProfile.objects.all_users().count() == 0,
        'create_command': django_settings.MAAS_CLI,
        }
    if request.user.is_authenticated():
        return HttpResponseRedirect(reverse('index'))
    else:
        return dj_login(request, extra_context=extra_context)


class LogoutForm(forms.Form):
    """Log-out confirmation form.

    There is nothing interesting in this form, but it's needed in order
    to get Django's CSRF protection during logout.
    """


def logout(request):
    if request.method == 'POST':
        form = LogoutForm(request.POST)
        if form.is_valid():
            messages.info(request, "You have been logged out.")
            return dj_logout(request, next_page=reverse('login'))
    else:
        form = LogoutForm()

    return render_to_response(
        'maasserver/logout_confirm.html',
        {'form': form},
        context_instance=RequestContext(request),
    )
