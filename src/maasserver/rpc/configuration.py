# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to configuration settings."""


from urllib.parse import urlparse

from maasserver.models.config import Config
from maasserver.utils.orm import transactional
from provisioningserver.utils.twisted import synchronous


@synchronous
@transactional
def get_proxies():
    """Obtain the HTTP and HTTPS proxy to use by clusters.

    Returns them as a structure suitable for returning in the response
    for :py:class:`~provisioningserver.rpc.region.GetProxies`.
    """
    if Config.objects.get_config("enable_http_proxy"):
        http_proxy = Config.objects.get_config("http_proxy")
        if http_proxy is not None:
            http_proxy = urlparse(http_proxy)
    else:
        http_proxy = None
    return {"http": http_proxy, "https": http_proxy}
