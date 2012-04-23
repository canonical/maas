# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Account views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "login",
    "logout",
    ]

from maasserver.models import UserProfile
from django.contrib.auth.views import (
    login as dj_login,
    logout as dj_logout,
    )
from django.contrib import messages
from django.conf import settings as django_settings
from django.core.urlresolvers import reverse


def login(request):
    extra_context = {
        'no_users': UserProfile.objects.all_users().count() == 0,
        'create_command': django_settings.MAAS_CLI,
        }
    return dj_login(request, extra_context=extra_context)


def logout(request):
    messages.info(request, "You have been logged out.")
    return dj_logout(request, next_page=reverse('login'))
