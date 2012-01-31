# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    print_function,
    unicode_literals,
    )

"""Access middleware."""

__metaclass__ = type
__all__ = [
    "AccessMiddleware",
    ]

import re

from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.utils.http import urlquote_plus


class AccessMiddleware(object):
    """Protect access to views.

    - login/logout/api-doc urls: authorize unconditionally
    - static resources urls: authorize unconditionally
    - API urls: deny (Forbidden error - 401) anonymous requests
    - views urls: redirect anonymous requests to login page
    """

    def __init__(self):
        self.public_urls = re.compile(
            "|".join(
                (reverse('login'),
                 reverse('logout'),
                 reverse('favicon'),
                 reverse('robots'),
                 reverse('api-doc'),
                 settings.API_URL_REGEXP,  # API calls are protected by piston.
                 settings.STATIC_URL)))
        self.login_url = reverse('login')

    def process_request(self, request):
        # Public urls.
        if self.public_urls.match(request.path):
            return None
        else:
            if request.user.is_anonymous():
                return HttpResponseRedirect("%s?next=%s" % (
                    self.login_url, urlquote_plus(request.path)))
            else:
                return None
