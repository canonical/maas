# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    print_function,
    unicode_literals,
    )

"""Context processors."""

__metaclass__ = type
__all__ = [
    "yui",
    ]

from django.conf import settings


def yui(context):
    return {
        'YUI_DEBUG': settings.YUI_DEBUG,
        'YUI_VERSION': settings.YUI_VERSION,
    }
