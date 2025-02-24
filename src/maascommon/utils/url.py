#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from urllib.parse import urlparse


def splithost(host: str) -> tuple[str, int]:
    """Split `host` into hostname and port.

    If no :port is in `host` the port with return as None.
    """
    parsed = urlparse("//" + host)
    hostname = parsed.hostname
    if hostname is None:
        # This only occurs when the `host` is an IPv6 address without brakets.
        # Lets try again but add the brackets.
        parsed = urlparse("//[%s]" % host)
        hostname = parsed.hostname
    if ":" in hostname:
        # IPv6 hostname, place back into brackets.
        hostname = "[%s]" % hostname
    return hostname, parsed.port
