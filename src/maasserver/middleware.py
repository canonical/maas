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

    Most UI views are visible only to logged-in users, but there are pages
    that are accessible to anonymous users (e.g. the login page!) or that
    use other authentication (e.g. the MaaS API, which is managed through
    piston).
    """

    def __init__(self):
        # URL prefixes that do not require authentication by Django.
        public_url_roots = [
            # Login/logout pages: must be visible to anonymous users.
            reverse('login'),
            reverse('logout'),
            # Static resources are publicly visible.
            settings.STATIC_URL,
            reverse('favicon'),
            reverse('robots'),
            reverse('api-doc'),
            # Metadata service is for use by nodes; no login.
            reverse('metadata'),
            # API calls are protected by piston.
            settings.API_URL_REGEXP,
            ]
        self.public_urls = re.compile("|".join(public_url_roots))
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
