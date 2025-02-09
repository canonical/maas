# Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Proxy config management module."""

from django.conf import settings
from twisted.internet.defer import succeed

from maasserver.models import Config
from maasserver.models.subnet import Subnet
from maasserver.service_monitor import service_monitor
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.logger import get_maas_logger
from provisioningserver.proxy.config import write_config
from provisioningserver.utils import snap
from provisioningserver.utils.twisted import asynchronous

maaslog = get_maas_logger("dns")
MAAS_PROXY_CONF_NAME = "maas-proxy.conf"
MAAS_PROXY_CONF_TEMPLATE = "maas-proxy.conf.template"


def is_proxy_enabled():
    """Is MAAS configured to manage the PROXY?"""
    return settings.PROXY_CONNECT


@asynchronous
def proxy_update_config(reload_proxy=True):
    """Regenerate the proxy configuration file."""

    @transactional
    def _write_config():
        allowed_subnets = Subnet.objects.filter(allow_proxy=True)
        cidrs = [subnet.cidr for subnet in allowed_subnets]
        config = Config.objects.get_configs(
            [
                "http_proxy",
                "maas_proxy_port",
                "use_peer_proxy",
                "prefer_v4_proxy",
                "enable_http_proxy",
            ]
        )

        kwargs = {
            "prefer_v4_proxy": config["prefer_v4_proxy"],
            "maas_proxy_port": config["maas_proxy_port"],
        }
        if (
            config["enable_http_proxy"]
            and config["http_proxy"]
            and config["use_peer_proxy"]
        ):
            kwargs["peer_proxies"] = [config["http_proxy"]]
        write_config(cidrs, **kwargs)

    if is_proxy_enabled():
        d = deferToDatabase(_write_config)
        if reload_proxy:
            # XXX: andreserl 2016-05-09 bug=1687620. When running in a snap,
            # supervisord tracks services. It does not support reloading.
            # Instead, we need to restart the service.
            if snap.running_in_snap():
                d.addCallback(
                    lambda _: service_monitor.restartService(
                        "proxy", if_on=True
                    )
                )
            else:
                d.addCallback(
                    lambda _: service_monitor.reloadService(
                        "proxy", if_on=True
                    )
                )
        return d
    else:
        return succeed(None)
