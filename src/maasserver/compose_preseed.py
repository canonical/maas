# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Low-level composition code for preseeds."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'compose_preseed',
    ]

from urllib import urlencode

from maasserver.enum import PRESEED_TYPE
from maasserver.utils import absolute_reverse
from provisioningserver.drivers.osystem import OperatingSystemRegistry
import yaml


def compose_cloud_init_preseed(token, base_url=''):
    """Compose the preseed value for a node in any state but Commissioning."""
    credentials = urlencode({
        'oauth_consumer_key': token.consumer.key,
        'oauth_token_key': token.key,
        'oauth_token_secret': token.secret,
        })

    local_config_yaml = yaml.safe_dump({
        "manage_etc_hosts": "localhost",
        "apt_preserve_sources_list": True,
    })
    # this is debconf escaping
    local_config = local_config_yaml.replace("\\", "\\\\").replace("\n", "\\n")

    # Preseed data to send to cloud-init.  We set this as MAAS_PRESEED in
    # ks_meta, and it gets fed straight into debconf.
    preseed_items = [
        ('datasources', 'multiselect', 'MAAS'),
        ('maas-metadata-url', 'string', absolute_reverse(
            'metadata', base_url=base_url)),
        ('maas-metadata-credentials', 'string', credentials),
        ('local-cloud-config', 'string', local_config)
        ]

    return '\n'.join(
        "cloud-init   cloud-init/%s  %s %s" % (
            item_name,
            item_type,
            item_value,
            )
        for item_name, item_type, item_value in preseed_items)


def compose_commissioning_preseed(token, base_url=''):
    """Compose the preseed value for a Commissioning node."""
    metadata_url = absolute_reverse('metadata', base_url=base_url)
    return _compose_cloud_init_preseed(token, metadata_url)


def compose_curtin_preseed(token, base_url=''):
    """Compose the preseed value for a node being installed with curtin."""
    metadata_url = absolute_reverse('curtin-metadata', base_url=base_url)
    return _compose_cloud_init_preseed(token, metadata_url)


def _compose_cloud_init_preseed(token, metadata_url):
    return "#cloud-config\n%s" % yaml.safe_dump({
        'datasource': {
            'MAAS': {
                'metadata_url': metadata_url,
                'consumer_key': token.consumer.key,
                'token_key': token.key,
                'token_secret': token.secret,
            }
        }
    })


def compose_preseed(preseed_type, node):
    """Put together preseed data for `node`.

    This produces preseed data for the node in different formats depending
    on the preseed_type.

    :param preseed_type: The type of preseed to compose.
    :type preseed_type: string
    :param node: The node to compose preseed data for.
    :type node: Node
    :return: Preseed data containing the information the node needs in order
        to access the metadata service: its URL and auth token.
    """
    # Circular import.
    from metadataserver.models import NodeKey
    token = NodeKey.objects.get_token_for_node(node)
    base_url = node.nodegroup.maas_url
    if preseed_type == PRESEED_TYPE.COMMISSIONING:
        return compose_commissioning_preseed(token, base_url)
    else:
        osystem = OperatingSystemRegistry[node.get_osystem()]
        metadata_url = absolute_reverse('metadata', base_url=base_url)
        if preseed_type == PRESEED_TYPE.CURTIN:
            metadata_url = absolute_reverse(
                'curtin-metadata', base_url=base_url)
        try:
            return osystem.compose_preseed(
                preseed_type, node, token, metadata_url)
        except NotImplementedError:
            pass

        if preseed_type == PRESEED_TYPE.CURTIN:
            return compose_curtin_preseed(token, base_url)
        else:
            return compose_cloud_init_preseed(token, base_url)
