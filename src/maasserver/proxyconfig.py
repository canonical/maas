# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Proxy config management module."""

__all__ = [
    'proxy_update_config',
    'get_proxy_config_path',
    'is_config_present',
    ]

import datetime
import os
import socket
import sys
from urllib.parse import urlparse

from django.conf import settings
from maasserver.models import Config
from maasserver.models.subnet import Subnet
from maasserver.service_monitor import service_monitor
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils import (
    locate_template,
    snappy,
)
from provisioningserver.utils.fs import atomic_write
from provisioningserver.utils.twisted import asynchronous
import tempita
from twisted.internet.defer import succeed


maaslog = get_maas_logger("dns")
MAAS_PROXY_CONF_NAME = 'maas-proxy.conf'
MAAS_PROXY_CONF_TEMPLATE = 'maas-proxy.conf.template'


def is_proxy_enabled():
    """Is MAAS configured to manage the PROXY?"""
    return settings.PROXY_CONNECT


class ProxyConfigFail(Exception):
    """Raised if there is a problem with the proxy configuration."""


def get_proxy_config_path():
    """Location of bind configuration files."""
    setting = os.getenv("MAAS_PROXY_CONFIG_DIR", "/var/lib/maas")
    if isinstance(setting, bytes):
        fsenc = sys.getfilesystemencoding()
        setting = setting.decode(fsenc)
    setting = os.sep.join([setting, MAAS_PROXY_CONF_NAME])
    return setting


def is_config_present():
    """Check if there is a configuration file for the proxy."""
    return os.access(get_proxy_config_path(), os.R_OK)


@asynchronous
def proxy_update_config(reload_proxy=True):
    """Regenerate the proxy configuration file."""

    @transactional
    def write_config():
        allowed_subnets = Subnet.objects.filter(allow_proxy=True)
        cidrs = [subnet.cidr for subnet in allowed_subnets]

        http_proxy = Config.objects.get_config("http_proxy")
        upstream_proxy_enabled = (
            Config.objects.get_config("use_peer_proxy") and http_proxy)
        dns_v4_first = Config.objects.get_config("prefer_v4_proxy")
        context = {
            'allowed': allowed_subnets,
            'modified': str(datetime.date.today()),
            'fqdn': socket.getfqdn(),
            'cidrs': cidrs,
            'running_in_snap': snappy.running_in_snap(),
            'snap_path': snappy.get_snap_path(),
            'snap_data_path': snappy.get_snap_data_path(),
            'snap_common_path': snappy.get_snap_common_path(),
            'upstream_peer_proxy': upstream_proxy_enabled,
            'dns_v4_first': dns_v4_first,
        }

        proxy_enabled = Config.objects.get_config("enable_http_proxy")
        if proxy_enabled and upstream_proxy_enabled:
            http_proxy_hostname = urlparse(http_proxy).hostname
            http_proxy_port = urlparse(http_proxy).port
            context.update({
                'upstream_proxy_address': http_proxy_hostname,
                'upstream_proxy_port': http_proxy_port,
            })

        template_path = locate_template('proxy', MAAS_PROXY_CONF_TEMPLATE)
        template = tempita.Template.from_filename(
            template_path, encoding="UTF-8")
        try:
            content = template.substitute(context)
        except NameError as error:
            raise ProxyConfigFail(*error.args)
        # Squid prefers ascii.
        content = content.encode("ascii")
        target_path = get_proxy_config_path()
        atomic_write(content, target_path, overwrite=True, mode=0o644)

    if is_proxy_enabled():
        d = deferToDatabase(write_config)
        if reload_proxy:
            # XXX: andreserl 2016-05-09 bug=1687620. When running in a snap,
            # supervisord tracks services. It does not support reloading.
            # Instead, we need to restart the service.
            if snappy.running_in_snap():
                d.addCallback(
                    lambda _: service_monitor.restartService(
                        "proxy", if_on=True))
            else:
                d.addCallback(
                    lambda _: service_monitor.reloadService(
                        "proxy", if_on=True))
        return d
    else:
        return succeed(None)
