# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to operating systems."""


from provisioningserver.drivers.osystem import (
    Node,
    OperatingSystemRegistry,
    Token,
)
from provisioningserver.rpc import exceptions


def gen_operating_system_releases(osystem):
    """Yield operating system release dicts.

    Each dict adheres to the response specification of an operating
    system release in the ``ListOperatingSystems`` RPC call.

    The releases are sorted by name to ensure deterministic results
    across multile calls.
    """
    releases_for_commissioning = set(
        osystem.get_supported_commissioning_releases()
    )
    for release in sorted(osystem.get_supported_releases()):
        requires_license_key = osystem.requires_license_key(release)
        can_commission = release in releases_for_commissioning
        yield {
            "name": release,
            "title": osystem.get_release_title(release),
            "requires_license_key": requires_license_key,
            "can_commission": can_commission,
        }


def gen_operating_systems():
    """Yield operating system dicts.

    Each dict adheres to the response specification of an operating
    system in the ``ListOperatingSystems`` RPC call.
    """

    for _, os in sorted(OperatingSystemRegistry):
        default_release = os.get_default_release()
        default_commissioning_release = os.get_default_commissioning_release()
        yield {
            "name": os.name,
            "title": os.title,
            "releases": gen_operating_system_releases(os),
            "default_release": default_release,
            "default_commissioning_release": default_commissioning_release,
        }


def get_os_release_title(osystem, release):
    """Get the title for the operating systems release.

    :raises NoSuchOperatingSystem: If ``osystem`` is not found.
    """
    try:
        osystem = OperatingSystemRegistry[osystem]
    except KeyError:
        raise exceptions.NoSuchOperatingSystem(osystem)
    else:
        title = osystem.get_release_title(release)
        if title is None:
            return ""
        return title


def validate_license_key(osystem, release, key):
    """Validate a license key.

    :raises NoSuchOperatingSystem: If ``osystem`` is not found.
    """
    try:
        osystem = OperatingSystemRegistry[osystem]
    except KeyError:
        raise exceptions.NoSuchOperatingSystem(osystem)
    else:
        return osystem.validate_license_key(release, key)


def get_preseed_data(
    osystem,
    preseed_type,
    node_system_id,
    node_hostname,
    consumer_key,
    token_key,
    token_secret,
    metadata_url,
):
    """Composes preseed data for the given node.

    :param preseed_type: The preseed type being composed.
    :param node: The node for which a preseed is being composed.
    :param token: OAuth token for the metadata URL.
    :param metadata_url: The metdata URL for the node.
    :type metadata_url: :py:class:`urlparse.ParseResult`
    :return: Preseed data for the given node.
    :raise NotImplementedError: when the specified operating system does
        not require custom preseed data.
    """
    try:
        osystem = OperatingSystemRegistry[osystem]
    except KeyError:
        raise exceptions.NoSuchOperatingSystem(osystem)
    else:
        return osystem.compose_preseed(
            preseed_type,
            Node(node_system_id, node_hostname),
            Token(consumer_key, token_key, token_secret),
            metadata_url.geturl(),
        )
