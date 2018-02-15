# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Combo view."""

__all__ = [
    'get_combo_view',
    ]

from functools import partial
import os

from convoy.combo import (
    combine_files,
    parse_qs,
)
from django.conf import settings
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotFound,
    HttpResponseRedirect,
)


MERGE_VIEWS = {
    "jquery.js": {
        "location": settings.JQUERY_LOCATION,
        "content_type": "text/javascript; charset=UTF-8",
        "files": [
            "jquery.min.js",
        ]
    },
    "angular.js": {
        "location": settings.ANGULARJS_LOCATION,
        "content_type": "text/javascript; charset=UTF-8",
        "files": [
            "angular.min.js",
            "angular-route.min.js",
            "angular-cookies.min.js",
            "angular-sanitize.min.js",
        ]
    },
    "ng-tags-input.js": {
        "content_type": "text/javascript; charset=UTF-8",
        "files": [
            "js/angular/3rdparty/ng-tags-input.js",
        ]
    },
    "sticky.js": {
        "content_type": "text/javascript; charset=UTF-8",
        "files": [
            "js/angular/3rdparty/sticky.js",
        ]
    },
    "vs-repeat.js": {
        "content_type": "text/javascript; charset=UTF-8",
        "files": [
            "js/angular/3rdparty/vs-repeat.js",
        ]
    },
    "maas-angular.js": {
        "content_type": "text/javascript; charset=UTF-8",
        "files": [
            "js/angular/maas.js",
            "js/angular/factories/bootresources.js",
            "js/angular/factories/configs.js",
            "js/angular/factories/controllers.js",
            "js/angular/factories/devices.js",
            "js/angular/factories/dhcpsnippets.js",
            "js/angular/factories/discoveries.js",
            "js/angular/factories/domains.js",
            "js/angular/factories/events.js",
            "js/angular/factories/fabrics.js",
            "js/angular/factories/general.js",
            "js/angular/factories/ipranges.js",
            "js/angular/factories/machines.js",
            "js/angular/factories/node_results.js",
            "js/angular/factories/nodes.js",
            "js/angular/factories/notifications.js",
            "js/angular/factories/packagerepositories.js",
            "js/angular/factories/pods.js",
            "js/angular/factories/region.js",
            "js/angular/factories/scripts.js",
            "js/angular/factories/services.js",
            "js/angular/factories/spaces.js",
            "js/angular/factories/sshkeys.js",
            "js/angular/factories/staticroutes.js",
            "js/angular/factories/subnets.js",
            "js/angular/factories/switches.js",
            "js/angular/factories/tags.js",
            "js/angular/factories/users.js",
            "js/angular/factories/vlans.js",
            "js/angular/factories/zones.js",
            "js/angular/services/search.js",
            "js/angular/services/manager.js",
            "js/angular/services/managerhelper.js",
            "js/angular/services/pollingmanager.js",
            "js/angular/services/error.js",
            "js/angular/services/validation.js",
            "js/angular/services/browser.js",
            "js/angular/services/converter.js",
            "js/angular/services/json.js",
            "js/angular/services/log.js",
            "js/angular/directives/accordion.js",
            "js/angular/directives/boot_images.js",
            "js/angular/directives/call_to_action.js",
            "js/angular/directives/card_loader.js",
            "js/angular/directives/code_lines.js",
            "js/angular/directives/contenteditable.js",
            "js/angular/directives/controller_image_status.js",
            "js/angular/directives/controller_status.js",
            "js/angular/directives/dbl_click_overlay.js",
            "js/angular/directives/enter.js",
            "js/angular/directives/enter_blur.js",
            "js/angular/directives/error_overlay.js",
            "js/angular/directives/error_toggle.js",
            "js/angular/directives/ipranges.js",
            "js/angular/directives/maas_obj_form.js",
            "js/angular/directives/mac_address.js",
            "js/angular/directives/machines_table.js",
            "js/angular/directives/notifications.js",
            "js/angular/directives/os_select.js",
            "js/angular/directives/placeholder.js",
            "js/angular/directives/pod_parameters.js",
            "js/angular/directives/power_parameters.js",
            "js/angular/directives/proxy_settings.js",
            "js/angular/directives/release_name.js",
            "js/angular/directives/release_options.js",
            "js/angular/directives/script_results_list.js",
            "js/angular/directives/script_runtime.js",
            "js/angular/directives/script_select.js",
            "js/angular/directives/script_status.js",
            "js/angular/directives/ssh_keys.js",
            "js/angular/directives/switches_table.js",
            "js/angular/directives/toggle_control.js",
            "js/angular/directives/type.js",
            "js/angular/directives/version_reloader.js",
            "js/angular/directives/window_width.js",
            "js/angular/filters/nodes.js",
            "js/angular/filters/by_fabric.js",
            "js/angular/filters/by_vlan.js",
            "js/angular/filters/by_space.js",
            "js/angular/filters/by_subnet.js",
            "js/angular/filters/order_by_date.js",
            "js/angular/filters/remove_default_vlan.js",
            "js/angular/controllers/nodes_list.js",
            "js/angular/controllers/add_hardware.js",
            "js/angular/controllers/add_device.js",
            "js/angular/controllers/add_domain.js",
            "js/angular/controllers/dashboard.js",
            "js/angular/controllers/images.js",
            "js/angular/controllers/intro.js",
            "js/angular/controllers/intro_user.js",
            "js/angular/controllers/node_details.js",
            "js/angular/controllers/node_details_networking.js",
            "js/angular/controllers/node_details_storage.js",
            "js/angular/controllers/node_details_storage_filesystems.js",
            "js/angular/controllers/node_events.js",
            "js/angular/controllers/node_result.js",
            "js/angular/controllers/node_results.js",
            "js/angular/controllers/pods_list.js",
            "js/angular/controllers/pod_details.js",
            "js/angular/controllers/domains_list.js",
            "js/angular/controllers/domain_details.js",
            "js/angular/controllers/fabric_details.js",
            "js/angular/controllers/networks_list.js",
            "js/angular/controllers/prefs.js",
            "js/angular/controllers/settings.js",
            "js/angular/controllers/subnet_details.js",
            "js/angular/controllers/vlan_details.js",
            "js/angular/controllers/space_details.js",
            "js/angular/controllers/zone_details.js",
            "js/angular/controllers/zones_list.js",
        ]
    },
    "yui.js": {
        "location": settings.YUI_LOCATION,
        "content_type": "text/javascript; charset=UTF-8",
        "files": [
            "yui-base/yui-base-min.js",
        ]
    },
    "maas-yui.js": {
        "content_type": "text/javascript; charset=UTF-8",
        "files": [
            "js/io.js",
            "js/prefs.js",
            "js/shortpoll.js",
            "js/enums.js",
        ]
    },
    "maas-settings-yui.js": {
        "content_type": "text/javascript; charset=UTF-8",
        "files": [
            "js/reveal.js",
            "js/os_distro_select.js",
        ]
    },
}


def get_absolute_location(location=''):
    """Return the absolute location of a static resource.

    This utility exist to deal with the various places where MAAS can find
    static resources.

    If the given location is an absolute location, return it. If not, treat
    the location as a relative location.

    :param location: An optional absolute or relative location.
    :type location: unicode
    :return: The absolute path.
    :rtype: unicode
    """
    if location.startswith(os.path.sep):
        return location
    else:
        return os.path.join(settings.STATIC_ROOT, location)


def get_combo_view(location='', default_redirect=None):
    """Return a Django view to serve static resources using a combo loader.

    :param location: An optional absolute or relative location.
    :type location: unicode
    :param default_redirect: An optional address where requests for one file
        of an unknown file type will be redirected.  If this parameter is
        omitted, such requests will lead to a "Bad request" response.
    :type location: unicode
    :return: A Django view method.
    :rtype: callable
    """
    location = get_absolute_location(location)
    return partial(
        combo_view, location=location, default_redirect=default_redirect)


def combo_view(request, location, default_redirect=None, encoding='utf8'):
    """Handle a request for combining a set of files.

    The files are searched in the absolute location `abs_location` (if
    defined) or in the relative location `rel_location`.
    """
    fnames = parse_qs(request.META.get("QUERY_STRING", ""))

    if fnames:
        if fnames[0].endswith('.js'):
            content_type = 'text/javascript; charset=UTF-8'
        elif fnames[0].endswith('.css'):
            content_type = 'text/css'
        elif default_redirect is not None and len(fnames) == 1:
            return HttpResponseRedirect(
                "%s%s" % (default_redirect, fnames[0]))
        else:
            return HttpResponseBadRequest(
                "Invalid file type requested.",
                content_type="text/plain; charset=UTF-8")
        content = "".join(
            [content.decode(encoding) for content in combine_files(
                fnames, location, resource_prefix='/', rewrite_urls=True)])

        return HttpResponse(
            content_type=content_type, status=200, content=content)

    return HttpResponseNotFound()


def merge_view(request, filename):
    """Merge the `files` from `location` into one file. Return the HTTP
    response with `content_type`.
    """
    merge_info = MERGE_VIEWS.get(filename, None)
    if merge_info is None:
        return HttpResponseNotFound()
    location = merge_info.get("location", None)
    if location is None:
        location = get_absolute_location()
    content = "".join(
        [content.decode('utf-8') for content in combine_files(
            merge_info["files"], location,
            resource_prefix='/', rewrite_urls=True)])
    return HttpResponse(
        content_type=merge_info["content_type"], status=200, content=content)
