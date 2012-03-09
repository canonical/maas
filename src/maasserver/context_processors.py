# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Context processors."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "yui",
    ]

from django.conf import settings
from maasserver.models import Config


def yui(context):
    return {
        'YUI_DEBUG': settings.YUI_DEBUG,
        'YUI_VERSION': settings.YUI_VERSION,
        'YUI_COMBO_URL': settings.YUI_COMBO_URL,
        'FORCE_SCRIPT_NAME': settings.FORCE_SCRIPT_NAME,
    }


def global_options(context):
    return {
        'global_options': {
            'site_name': Config.objects.get_config('maas_name'),
        }
    }
