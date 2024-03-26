# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers for dealing with tags."""


from apiclient.maas_client import MAASClient, MAASDispatcher, MAASOAuth
from provisioningserver.tags import process_node_tags
from provisioningserver.utils.twisted import synchronous


@synchronous
def evaluate_tag(
    system_id,
    nodes,
    tag_name,
    tag_definition,
    tag_nsmap,
    credentials,
    maas_url,
):
    """Evaluate `tag_definition` against this cluster's nodes' details.

    :param system_id: System ID for the rack controller.
    :param nodes: List of nodes to evaluate.
    :param tag_name: The name of the tag, used for logging.
    :param tag_definition: The XPath expression of the tag.
    :param tag_nsmap: The namespace map as used by LXML's ETree library.
    :param credentials: A 3-tuple of OAuth credentials.
    :param maas_url: URL of the MAAS API.
    """
    # Turn off proxy detection, since the rack should talk directly to
    # the region, even if a system-wide proxy is configured.
    client = MAASClient(
        auth=MAASOAuth(*credentials),
        dispatcher=MAASDispatcher(autodetect_proxies=False),
        base_url=maas_url,
        insecure=True,
    )
    process_node_tags(
        rack_id=system_id,
        nodes=nodes,
        tag_name=tag_name,
        tag_definition=tag_definition,
        tag_nsmap=tag_nsmap,
        client=client,
    )
