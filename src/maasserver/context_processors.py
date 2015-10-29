# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
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
from maasserver.components import get_persistent_errors
from maasserver.models import Config
from maasserver.utils.version import (
    get_maas_doc_version,
    get_maas_version_ui,
)


def yui(context):
    return {
        'YUI_DEBUG': settings.YUI_DEBUG,
    }


def static_resources(context):
    return {
        'CSS_LIST': [
            'css/base.css',
            'css/maas-styles.css',
        ],
        'ANGULAR_LIST': [
            'js/angular/maas.js',
            'js/angular/factories/region.js',
            'js/angular/factories/nodes.js',
            'js/angular/factories/devices.js',
            'js/angular/factories/clusters.js',
            'js/angular/factories/zones.js',
            'js/angular/factories/general.js',
            'js/angular/factories/users.js',
            'js/angular/factories/events.js',
            'js/angular/factories/tags.js',
            'js/angular/factories/subnets.js',
            'js/angular/factories/spaces.js',
            'js/angular/factories/vlans.js',
            'js/angular/factories/fabrics.js',
            'js/angular/services/search.js',
            'js/angular/services/manager.js',
            'js/angular/services/managerhelper.js',
            'js/angular/services/error.js',
            'js/angular/services/validation.js',
            'js/angular/services/browser.js',
            'js/angular/services/converter.js',
            'js/angular/directives/error_overlay.js',
            'js/angular/directives/code_lines.js',
            'js/angular/directives/error_toggle.js',
            'js/angular/directives/call_to_action.js',
            'js/angular/directives/power_parameters.js',
            'js/angular/directives/os_select.js',
            'js/angular/directives/type.js',
            'js/angular/directives/accordion.js',
            'js/angular/directives/dbl_click_overlay.js',
            'js/angular/directives/contenteditable.js',
            'js/angular/directives/sticky_header.js',
            'js/angular/directives/placeholder.js',
            'js/angular/directives/enter_blur.js',
            'js/angular/directives/version_reloader.js',
            'js/angular/filters/nodes.js',
            'js/angular/filters/by_fabric.js',
            'js/angular/filters/by_vlan.js',
            'js/angular/filters/by_space.js',
            'js/angular/filters/remove_default_vlan.js',
            'js/angular/controllers/error.js',
            'js/angular/controllers/nodes_list.js',
            'js/angular/controllers/add_hardware.js',
            'js/angular/controllers/add_device.js',
            'js/angular/controllers/node_details.js',
            'js/angular/controllers/node_details_networking.js',
            'js/angular/controllers/node_details_storage.js',
            'js/angular/controllers/node_result.js',
            'js/angular/controllers/node_events.js',
            'js/angular/controllers/subnets_list.js',
            'js/angular/controllers/subnet_details.js',
        ],
        'JS_LIST': [
            'js/image.js',
            'js/image_views.js',
            'js/user_panel.js',
            'js/prefs.js',
            'js/shortpoll.js',
            'js/enums.js',
            'js/reveal.js',
            'js/os_distro_select.js',
        ],
    }


def global_options(context):
    return {
        'persistent_errors': get_persistent_errors(),
        'global_options': {
            'site_name': Config.objects.get_config('maas_name'),
        },
        'debug': settings.DEBUG,
        'version': get_maas_version_ui(),
        'doc_version': get_maas_doc_version(),
    }
