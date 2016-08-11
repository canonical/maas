# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Monkey patch for the MAAS region server, with code for region server patching.
"""

__all__ = [
    "add_patches_to_django",
]

import re


fixed_re = re.compile(r"^([a-z0-9.-]+|\[[a-f0-9]*:[a-f0-9:\.]+\])(:\d+)?$")


def fix_django_http_request():
    """Add support for ipv6-formatted ipv4 addresses to django requests.

       See https://bugs.launchpad.net/ubuntu/+source/python-django/+bug/1611923
    """
    import django.http.request
    if not django.http.request.host_validation_re.match("[::ffff:127.0.0.1]"):
        django.http.request.host_validation_re = fixed_re


def add_patches_to_django():
    fix_django_http_request()
