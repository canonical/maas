# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Network utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'generated_hostname',
    ]


def generated_hostname(ip, domain=None):
    """Return the auto-generated hostname for the give IP.

    >>> generated_hostname('192.168.0.1')
    '192-168-0-1'
    >>> generated_hostname('192.168.0.1', 'mydomain.com')
    '192-168-0-1.mydomain.com'
    """
    hostname = ip.replace('.', '-')
    if domain is not None:
        return '%s.%s' % (hostname, domain)
    else:
        return hostname
