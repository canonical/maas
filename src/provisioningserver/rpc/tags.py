# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers for dealing with tags."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "evaluate_tag",
]

from apiclient.maas_client import (
    MAASClient,
    MAASDispatcher,
    MAASOAuth,
    )
from provisioningserver.cluster_config import (
    get_cluster_uuid,
    get_maas_url,
    )
from provisioningserver.tags import process_node_tags
from provisioningserver.utils.twisted import synchronous


@synchronous
def evaluate_tag(tag_name, tag_definition, tag_nsmap, credentials):
    """Evaluate `tag_definition` against this cluster's nodes' details.

    :param tag_name: The name of the tag, used for logging.
    :param tag_definition: The XPath expression of the tag.
    :param tag_nsmap: The namespace map as used by LXML's ETree library.
    :param credentials: A 3-tuple of OAuth credentials.
    """
    client = MAASClient(
        auth=MAASOAuth(*credentials), dispatcher=MAASDispatcher(),
        base_url=get_maas_url())
    process_node_tags(
        tag_name=tag_name, tag_definition=tag_definition, tag_nsmap=tag_nsmap,
        client=client, nodegroup_uuid=get_cluster_uuid())
