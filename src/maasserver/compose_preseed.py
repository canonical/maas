# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Low-level composition code for preseeds."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'compose_preseed',
    ]

from urllib import urlencode

from maasserver.enum import NODE_STATUS
from maasserver.utils import absolute_reverse
import yaml


def compose_cloud_init_preseed(token):
    """Compose the preseed value for a node in any state but Commissioning."""
    credentials = urlencode({
        'oauth_consumer_key': token.consumer.key,
        'oauth_token_key': token.key,
        'oauth_token_secret': token.secret,
        })

    # Preseed data to send to cloud-init.  We set this as MAAS_PRESEED in
    # ks_meta, and it gets fed straight into debconf.
    metadata_preseed_items = [
        ('datasources', 'multiselect', 'MAAS'),
        ('maas-metadata-url', 'string', absolute_reverse('metadata')),
        ('maas-metadata-credentials', 'string', credentials),
        ]

    return '\n'.join(
        "cloud-init   cloud-init/%s  %s %s" % (
            item_name,
            item_type,
            item_value,
            )
        for item_name, item_type, item_value in metadata_preseed_items)


def compose_commissioning_preseed(token):
    """Compose the preseed value for a Commissioning node."""
    return "#cloud-config\n%s" % yaml.safe_dump({
        'datasource': {
            'MAAS': {
                'metadata_url': absolute_reverse('metadata'),
                'consumer_key': token.consumer.key,
                'token_key': token.key,
                'token_secret': token.secret,
            }
        }
    })


def compose_preseed(node):
    """Put together preseed data for `node`.

    This produces preseed data in different formats depending on the node's
    state: if it's Commissioning, it boots into commissioning mode with its
    own profile, its own user_data, and also its own preseed format.  It's
    basically a network boot.
    Otherwise, it will get a different format that feeds directly into the
    installer.

    :param node: The node to compose preseed data for.
    :type node: Node
    :return: Preseed data containing the information the node needs in order
        to access the metadata service: its URL and auth token.
    """
    # Circular import.
    from metadataserver.models import NodeKey
    token = NodeKey.objects.get_token_for_node(node)
    if node.status == NODE_STATUS.COMMISSIONING:
        return compose_commissioning_preseed(token)
    else:
        return compose_cloud_init_preseed(token)
