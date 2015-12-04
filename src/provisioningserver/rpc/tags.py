# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers for dealing with tags."""

__all__ = [
    "evaluate_tag",
]

from apiclient.maas_client import (
    MAASClient,
    MAASDispatcher,
    MAASOAuth,
)
from provisioningserver.config import ClusterConfiguration
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
    with ClusterConfiguration.open() as config:
        cluster_uuid = config.cluster_uuid
        maas_url = config.maas_url
    client = MAASClient(
        auth=MAASOAuth(*credentials), dispatcher=MAASDispatcher(),
        base_url=maas_url)
    process_node_tags(
        tag_name=tag_name, tag_definition=tag_definition, tag_nsmap=tag_nsmap,
        client=client, nodegroup_uuid=cluster_uuid)
