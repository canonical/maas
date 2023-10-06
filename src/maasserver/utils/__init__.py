# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities."""

__all__ = [
    "absolute_reverse",
    "build_absolute_uri",
    "find_rack_controller",
    "get_maas_user_agent",
    "strip_domain",
    "synchronised",
]

from functools import lru_cache, wraps
import os
from typing import Tuple
from urllib.parse import urlencode, urljoin, urlsplit

from django.conf import settings
from django.urls import reverse
from netaddr import valid_ipv4, valid_ipv6
import tempita

from maasserver.config import RegionConfiguration
from provisioningserver.utils.network import get_source_address
from provisioningserver.utils.url import compose_URL
from provisioningserver.utils.version import get_running_version


def absolute_reverse(
    view_name,
    default_region_ip=None,
    query=None,
    base_url=None,
    *args,
    **kwargs,
):
    """Return the absolute URL (i.e. including the URL scheme specifier and
    the network location of the MAAS server).  Internally this method simply
    calls Django's 'reverse' method and prefixes the result of that call with
    the configured MAAS URL.

    For details on how to set the MAAS URL, consult the command:
    'maas-region local_config_set --default-url' for deb installs, or
    'maas config --maas-url' for snap installs.

    :param view_name: Django's view function name/reference or URL pattern
        name for which to compute the absolute URL.
    :param default_region_ip: The default source IP address that should be
        used for the region controller.
    :param query: Optional query argument which will be passed down to
        urllib.urlencode.  The result of that call will be appended to the
        resulting url.
    :param base_url: Optional url used as base.  If None is provided, then
        configured MAAS URL will be used.
    :param args: Positional arguments for Django's 'reverse' method.
    :param kwargs: Named arguments for Django's 'reverse' method.
    """
    if not base_url:
        with RegionConfiguration.open() as config:
            base_url = config.maas_url
        if default_region_ip is not None:
            base_url = compose_URL(base_url, default_region_ip)
    if not base_url.endswith("/"):
        # Add trailing '/' to get urljoin to behave.
        base_url = base_url + "/"
    if view_name.startswith("/"):
        reverse_link = view_name
    else:
        reverse_link = reverse(view_name, *args, **kwargs)
    if reverse_link.startswith("/"):
        # Drop the leading '/'.
        reverse_link = reverse_link[1:]
    script_name = settings.FORCE_SCRIPT_NAME.lstrip("/")
    if base_url.endswith(script_name) and reverse_link.startswith(script_name):
        # This would double up the SCRIPT_NAME we only need one so remove the
        # prefix from the reverse_link.
        reverse_link = reverse_link[len(script_name) :]
    url = urljoin(base_url, reverse_link)
    if query is not None:
        url += "?%s" % urlencode(query, doseq=True)
    return url


def build_absolute_uri(request, path):
    """Return absolute URI corresponding to given absolute path.

    :param request: An http request to the API.  This is needed in order to
        figure out how the client is used to addressing
        the API on the network.
    :param path: The absolute http path to a given resource.
    :return: Full, absolute URI to the resource, taking its networking
        portion from `request` but the rest from `path`.
    """
    scheme = "https" if request.is_secure() else "http"
    return f"{scheme}://{request.get_host()}{path}"


def strip_domain(hostname):
    """Return `hostname` with the domain part removed."""
    return hostname.split(".", 1)[0]


def get_maas_user_agent():
    from maasserver.models import Config

    version = get_running_version()
    user_agent = f"maas/{version.short_version}/{version.extended_info}"
    uuid = Config.objects.get_config("uuid")
    if uuid:
        user_agent += f"/{uuid}"
    return user_agent


def get_host_without_port(http_host):
    return urlsplit("http://%s/" % http_host).hostname


def get_request_host(request):
    """Returns the Host header from the specified HTTP request."""
    request_host = request.headers.get("host")
    if request_host is not None:
        request_host = get_host_without_port(request_host)
    return request_host


def is_valid_ip(ip):
    """Check the validity of an IP address."""
    return valid_ipv4(ip) or valid_ipv6(ip)


def get_remote_ip(request):
    """Returns the IP address of the host that initiated the request."""
    # Try to obtain IP Address from X-Forwarded-For first.
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
        if is_valid_ip(ip):
            return ip

    ip = request.META.get("REMOTE_ADDR")
    return ip if is_valid_ip(ip) else None


def find_rack_controller(request):
    """Find the rack controller whose managing the subnet that contains the
    requester's address.

    There may be multiple matching rack controllers, but we choose the active
    rack controller for that subnet.
    """
    # Circular imports.
    from maasserver.models.subnet import Subnet

    ip_address = get_remote_ip(request)
    subnet = Subnet.objects.get_best_subnet_for_ip(ip_address)
    if subnet is None:
        return None
    if subnet.vlan.dhcp_on is False:
        return None
    return subnet.vlan.primary_rack


def synchronised(lock):
    """Decorator to synchronise a call against a given lock.

    Note: if the function being wrapped is a generator, the lock will
    *not* be held for the lifetime of the generator; to this decorator,
    it looks like the wrapped function has returned.
    """

    def synchronise(func):
        @wraps(func)
        def call_with_lock(*args, **kwargs):
            with lock:
                return func(*args, **kwargs)

        return call_with_lock

    return synchronise


def get_default_region_ip(request):
    """Returns the default reply address for the given HTTP request."""
    request_host = get_request_host(request)
    if request_host is not None:
        return request_host
    remote_ip = get_remote_ip(request)
    default_region_ip = None
    if remote_ip is not None:
        default_region_ip = get_source_address(remote_ip)
    return default_region_ip


@lru_cache(maxsize=256)
def load_template(*path: Tuple[str]):
    """Load the template."""
    return tempita.Template.from_filename(
        os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "templates", *path)
        ),
        encoding="UTF-8",
    )
