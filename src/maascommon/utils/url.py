#  Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from collections.abc import Collection
from ipaddress import IPv6Address
import re
from urllib.parse import urlparse, urlsplit

# The URL patterns are based on Django's URLValidator, as relaxed by
# maasserver.utils.dns.validate_url: hosts without a domain (e.g. http://foo)
# are accepted. Unlike the legacy validator, ports outside of 0-65535 are
# rejected.
_UNICODE_LETTERS = "\u00a1-\uffff"
_IPV4 = (
    r"(?:0|25[0-5]|2[0-4][0-9]|1[0-9]?[0-9]?|[1-9][0-9]?)"
    r"(?:\.(?:0|25[0-5]|2[0-4][0-9]|1[0-9]?[0-9]?|[1-9][0-9]?)){3}"
)
# Only a coarse check; the address itself is validated with ipaddress.
_IPV6 = r"\[[0-9a-f:.]+\]"
_LABEL = (
    rf"[a-z{_UNICODE_LETTERS}0-9]"
    rf"(?:[a-z{_UNICODE_LETTERS}0-9-]{{0,61}}[a-z{_UNICODE_LETTERS}0-9])?"
)
_DOMAIN = rf"(?:\.(?!-)[a-z{_UNICODE_LETTERS}0-9-]{{1,63}}(?<!-))*"
_TLD = (
    r"\.(?!-)"
    rf"(?:[a-z{_UNICODE_LETTERS}-]{{2,63}}|xn--[a-z0-9]{{1,59}})"
    r"(?<!-)\.?"
)
_HOST = rf"(?:{_LABEL}{_DOMAIN}{_TLD}|{_LABEL}|localhost)"
_URL_RE = re.compile(
    r"^[a-z0-9.+-]*://"  # The scheme is checked separately.
    r"(?:[^\s:@/]+(?::[^\s:@/]*)?@)?"  # user:password
    rf"(?:{_IPV4}|{_IPV6}|{_HOST})"
    r"(?::[0-9]{1,5})?"
    r"(?:[/?#]\S*)?"
    r"\Z",
    re.IGNORECASE,
)
_MAX_URL_LENGTH = 2048
# RFC 1034 section 3.1, excluding the length byte and the trailing dot.
_MAX_HOSTNAME_LENGTH = 253


def splithost(host: str) -> tuple[str | None, int | None]:
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
    if hostname is not None and ":" in hostname:
        # IPv6 hostname, place back into brackets.
        hostname = "[%s]" % hostname
    return hostname, parsed.port


def validate_url(
    url: str, schemes: Collection[str] = ("http", "https")
) -> None:
    if (
        not isinstance(url, str)
        or len(url) > _MAX_URL_LENGTH
        or not _URL_RE.match(url)
        or url.split("://")[0].lower() not in schemes
    ):
        raise ValueError(f"Invalid URL: {url!r}")
    try:
        split_url = urlsplit(url)
        hostname = split_url.hostname
        # Fails for ports outside of 0-65535.
        _ = split_url.port
    except ValueError as e:
        raise ValueError(f"Invalid URL: {url!r}") from e
    if hostname is None or len(hostname) > _MAX_HOSTNAME_LENGTH:
        raise ValueError(f"Invalid URL: {url!r}")
    if ":" in hostname:
        try:
            IPv6Address(hostname)
        except ValueError as e:
            raise ValueError(f"Invalid URL: {url!r}") from e
