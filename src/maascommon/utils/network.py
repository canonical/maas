# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import re


def coerce_to_valid_hostname(
    hostname: str, lowercase: bool = True
) -> str | None:
    """Given a server name that may contain spaces and special characters,
    attempts to derive a valid hostname.

    :param hostname: the specified (possibly invalid) hostname
    :param lowercase: whether to coerce to lowercase chars
    :return: the resulting string, or None if the hostname could not be coerced
    """
    if lowercase:
        hostname = hostname.lower()
    hostname = re.sub(r"[^a-zA-Z0-9-]+", "-", hostname)
    hostname = hostname.strip("-")
    if hostname == "" or len(hostname) > 64:
        return None
    return hostname
