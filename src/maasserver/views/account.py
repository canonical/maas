# Copyright 2012 Canonical Ltd.  This software is licensed under the
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

from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth.views import (
    login as dj_login,
    logout as dj_logout,
    )
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
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


def logout(request):
    messages.info(request, "You have been logged out.")
    return dj_logout(request, next_page=reverse('login'))
