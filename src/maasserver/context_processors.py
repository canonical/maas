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
    "global_options",
    "static_resources",
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
    }


def static_resources(context):
    return {
        'CSS_LIST': [
            'css/base.css',
            'css/typography.css',
            'css/forms.css',
            'css/layout.css',
            'css/modifiers.css',
            'css/components/flash_messages.css',
            'css/components/pagination.css',
            'css/components/table_list.css',
            'css/components/title_form.css',
            'css/components/blocks.css',
            'css/components/yui_panel.css',
            'css/components/yui_overlay.css',
            'css/components/yui_node_add.css',
            'css/components/data_list.css',
            'css/components/search_box.css',
            'css/ubuntu-webfonts.css',
        ],
        'JS_LIST': [
            'js/morph.js',
            'js/user_panel.js',
            'js/node_add.js',
            'js/node.js',
            'js/prefs.js',
            'js/utils.js',
            'js/node_views.js',
            'js/longpoll.js',
            'js/enums.js',
            'js/power_parameters.js',
            'js/nodes_chart.js',
        ],
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
