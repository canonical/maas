# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Context processors."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "yui",
    ]

from django.conf import settings
from maasserver.components import get_persistent_errors
from maasserver.forms import get_node_edit_form
from maasserver.models import Config
from maasserver.power_parameters import POWER_TYPE_PARAMETERS
from provisioningserver.enum import POWER_TYPE


def yui(context):
    return {
        'YUI_DEBUG': settings.YUI_DEBUG,
        'YUI_VERSION': settings.YUI_VERSION,
        'YUI_COMBO_URL': settings.YUI_COMBO_URL,
        'FORCE_SCRIPT_NAME': settings.FORCE_SCRIPT_NAME,
    }


def global_options(context):
    return {
        'persistent_errors': get_persistent_errors(),
        'node_form': get_node_edit_form(context.user)(),
        'POWER_TYPE_PARAMETERS_FIELDS':
            [(power_type, field.widget.render('power_parameters', []))
                for power_type, field in POWER_TYPE_PARAMETERS.items()
                if power_type is not POWER_TYPE.DEFAULT],
        'global_options': {
            'site_name': Config.objects.get_config('maas_name'),
        }
    }
