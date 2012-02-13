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

import json
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.http import (
    HttpResponseBadRequest,
    HttpResponseRedirect,
    )
from django.utils.http import urlquote_plus
from maasserver.exceptions import MaasAPIException


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


class APIErrorsMiddleware(object):
    """Convert exceptions raised in the API into a proper API error.

    - Convert MaasAPIException instances into the corresponding error.
    - Convert ValidationError into Bad Request.
    """
    def __init__(self):
        self.api_regexp = re.compile(settings.API_URL_REGEXP)

    def process_exception(self, request, exception):
        if self.api_regexp.match(request.path):
            # The exception was raised in an API call.
            if isinstance(exception, MaasAPIException):
                # The exception is a MaasAPIException: exception.api_error
                # will give us the proper error type.
                response = exception.api_error
                response.write(str(exception))
                return response
            if isinstance(exception, ValidationError):
                if hasattr(exception, 'message_dict'):
                    # Complex validation error with multiple fields:
                    # return a json version of the message_dict.
                    return HttpResponseBadRequest(
                        json.dumps(exception.message_dict),
                        content_type='application/json')
                else:
                    # Simple validation error: return the error message.
                    return HttpResponseBadRequest(str(exception))
