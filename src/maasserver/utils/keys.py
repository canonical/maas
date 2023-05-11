# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""keys-related utilities."""


import http
import logging
from typing import List

import requests

from maasserver.enum import KEYS_PROTOCOL_TYPE, KEYS_PROTOCOL_TYPE_CHOICES
from maasserver.models import Config

logging.getLogger("requests").setLevel(logging.WARNING)


class ImportSSHKeysError(Exception):
    """Importing SSH Keys failed."""


def get_proxies():
    """Return HTTP proxies."""
    proxies = None
    if Config.objects.get_config("enable_http_proxy"):
        http_proxy = Config.objects.get_config("http_proxy")
        if http_proxy:
            proxies = {"http": http_proxy, "https": http_proxy}
    return proxies


def get_protocol_keys(protocol: str, auth_id: str) -> List[str]:
    """Retrieve SSH Keys for auth_id using protocol."""
    if protocol == KEYS_PROTOCOL_TYPE.LP:
        keys = get_launchpad_ssh_keys(auth_id)
    elif protocol == KEYS_PROTOCOL_TYPE.GH:
        keys = get_github_ssh_keys(auth_id)
    if not keys:
        raise ImportSSHKeysError(
            "Unable to import SSH keys. "
            "There are no SSH keys for %s user %s."
            % (dict(KEYS_PROTOCOL_TYPE_CHOICES)[protocol], auth_id)
        )
    return keys


def get_launchpad_ssh_keys(auth_id: str) -> List[str]:
    """Retrieve SSH Keys from launchpad."""
    url = "https://launchpad.net/~%s/+sshkeys" % auth_id
    response = requests.get(url, proxies=get_proxies())
    # Check for 404 error which happens for an unknown user
    # or 410 for page gone.
    if response.status_code in (
        http.HTTPStatus.NOT_FOUND,
        http.HTTPStatus.GONE,
    ):
        raise ImportSSHKeysError(
            "Unable to import SSH keys. "
            "launchpad user %s doesn't exist." % auth_id
        )
    # If another type of HTTP error, need to force the raise
    response.raise_for_status()
    return [key for key in response.text.splitlines() if key]


def get_github_ssh_keys(auth_id: str) -> List[str]:
    """Retrieve SSH Keys from GitHub."""
    url = "https://api.github.com/users/%s/keys" % auth_id
    response = requests.get(url, proxies=get_proxies())
    # Check for 404 error which happens for an unknown user
    # or 410 for page gone.
    if response.status_code in (
        http.HTTPStatus.NOT_FOUND,
        http.HTTPStatus.GONE,
    ):
        raise ImportSSHKeysError(
            "Unable to import SSH keys. "
            "github user %s doesn't exist." % auth_id
        )
    # If another type of HTTP error, need to force the raise
    response.raise_for_status()
    # github returns JSON content
    return [data["key"] for data in response.json() if "key" in data]
