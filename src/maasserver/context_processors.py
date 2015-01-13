# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Context processors."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "global_options",
    "static_resources",
    "yui",
    ]

from django.conf import settings
from maasserver.clusterrpc.power_parameters import get_power_type_parameters
from maasserver.components import get_persistent_errors
from maasserver.forms import get_node_edit_form
from maasserver.models import Config


def yui(context):
    return {
        'YUI_DEBUG': settings.YUI_DEBUG,
    }


def static_resources(context):
    return {
        'CSS_LIST': [
            'css/maas-styles.css',
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
            'css/components/fluid.css',
            'css/components/yui_panel.css',
            'css/components/yui_overlay.css',
            'css/components/yui_node_add.css',
            'css/components/data_list.css',
            'css/components/search_box.css',
            'css/components/slider.css',
            'css/components/spinner.css',
            'css/ubuntu-webfonts.css',
            'css/multiselect_widget.css',
        ],
        'JS_LIST': [
            'js/image.js',
            'js/image_views.js',
            'js/license_key.js',
            'js/morph.js',
            'js/user_panel.js',
            'js/node_add.js',
            'js/node.js',
            'js/prefs.js',
            'js/utils.js',
            'js/node_views.js',
            'js/node_check.js',
            'js/shortpoll.js',
            'js/enums.js',
            'js/os_distro_select.js',
            'js/power_parameters.js',
            'js/nodes_chart.js',
            'js/reveal.js',
        ],
    }


def global_options(context):
    return {
        'persistent_errors': get_persistent_errors(),
        'node_form': get_node_edit_form(context.user)(),
        'POWER_TYPE_PARAMETERS_FIELDS': [
            (power_type, field.widget.render('power_parameters', []))
            for power_type, field in get_power_type_parameters().items()
        ],
        'global_options': {
            'site_name': Config.objects.get_config('maas_name'),
        },
        'debug': settings.DEBUG,
    }
