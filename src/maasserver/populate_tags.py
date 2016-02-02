# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Populate what nodes are associated with a tag."""

__all__ = [
    'populate_tags',
    'populate_tags_for_single_node',
    ]

from functools import partial

from apiclient.creds import convert_tuple_to_string
from lxml import etree
from maasserver import logger
from maasserver.models.node import (
    Node,
    RackController,
)
from maasserver.models.nodeprobeddetails import (
    get_single_probed_details,
    script_output_nsmap,
)
from maasserver.models.user import get_creds_tuple
from maasserver.rpc import getAllClients
from metadataserver.models.nodekey import NodeKey
from provisioningserver.logger import get_maas_logger
from provisioningserver.rpc.cluster import EvaluateTag
from provisioningserver.tags import merge_details
from provisioningserver.utils import classify
from provisioningserver.utils.twisted import (
    asynchronous,
    FOREVER,
    synchronous,
)
from provisioningserver.utils.xpath import try_match_xpath
from twisted.internet.defer import DeferredList
from twisted.python import log


maaslog = get_maas_logger("tags")


# The nsmap that XPath expression must be compiled with. This will
# ensure that expressions like //lshw:something will work correctly.
tag_nsmap = {
    namespace: namespace
    for namespace in script_output_nsmap.values()
}


def chunk_list(items, size):
    """Split `items` into multiple lists of maximum `size`."""
    for i in range(0, len(items), size):
        yield items[i:i + size]


@synchronous
def populate_tags(tag):
    """Evaluate `tag` for all nodes.

    This returns a `Deferred` that will fire when all tags have been
    evaluated. This is intended FOR TESTING ONLY because:

    - You must not use the `Deferred` in the calling thread; it must only be
      manipulated in the reactor thread. Pretending it's not there is safer
      than chaining code onto it because it's easy to get wrong.

    - The call may not finish for 10 minutes or more. It is therefore not a
      good thing to be waiting for in a web request.

    """
    logger.debug('Evaluating the "%s" tag for all nodes.', tag.name)
    clients = getAllClients()
    if len(clients) == 0:
        # XXX: allenap 2014-09-22 bug=1372544: No connected rack controllers.
        # Nothing can be evaluated when this occurs.
        return

    # Split the work between the connected rack controllers. Building all the
    # information that needs to be sent to them all.
    node_ids = Node.objects.all().values_list("system_id", flat=True)
    node_ids = [
        {"system_id": node_id}
        for node_id in node_ids
    ]
    chunk_size = int(len(node_ids) / len(clients))
    chunked_node_ids = list(chunk_list(node_ids, chunk_size))
    connected_racks = []
    for idx, client in enumerate(clients):
        rack = RackController.objects.get(system_id=client.ident)
        token = NodeKey.objects.get_token_for_node(rack)
        creds = convert_tuple_to_string(get_creds_tuple(token))
        connected_racks.append({
            "system_id": rack.system_id,
            "hostname": rack.hostname,
            "client": client,
            "tag_name": tag.name,
            "tag_definition": tag.definition,
            "tag_nsmap": [
                {"prefix": prefix, "uri": uri}
                for prefix, uri in tag_nsmap.items()
            ],
            "credentials": creds,
            "nodes": list(chunked_node_ids[idx]),
        })

    [d] = _do_populate_tags(connected_racks)
    return d


@asynchronous(timeout=FOREVER)
def _do_populate_tags(clients):
    """Send RPC calls to each rack controller, requesting evaluation of tags.

    :param clients: List of connected rack controllers that EvaluateTag
        will be called.
    """

    def call_client(client_info):
        client = client_info["client"]
        return client(
            EvaluateTag,
            tag_name=client_info["tag_name"],
            tag_definition=client_info["tag_definition"],
            tag_nsmap=client_info["tag_nsmap"],
            credentials=client_info["credentials"],
            nodes=client_info["nodes"])

    def check_results(results):
        for client_info, (success, result) in zip(clients, results):
            if success:
                maaslog.info(
                    "Tag %s (%s) evaluated on rack controller %s (%s)",
                    client_info['tag_name'],
                    client_info['tag_definition'],
                    client_info['hostname'],
                    client_info['system_id'])
            else:
                maaslog.error(
                    "Tag %s (%s) could not be evaluated on rack controller "
                    "%s (%s): %s",
                    client_info['tag_name'],
                    client_info['tag_definition'],
                    client_info['hostname'],
                    client_info['system_id'],
                    result.getErrorMessage())

    d = DeferredList((
        call_client(client_info)
        for client_info in clients),
        consumeErrors=True)
    d.addCallback(check_results)
    d.addErrback(log.err)

    # Do *not* return a Deferred; the caller is not meant to wait around for
    # this to finish. However, for the sake of testing, we return the Deferred
    # wrapped up in a list so that crochet does not block.
    return [d]


def populate_tags_for_single_node(tags, node):
    """Reevaluate all tags for a single node.

    Presumably this node's details have recently changed. Use
    `populate_tags` when many nodes need reevaluating.
    """
    probed_details = get_single_probed_details(node.system_id)
    probed_details_doc = merge_details(probed_details)
    # Same document, many queries: use XPathEvaluator.
    evaluator = etree.XPathEvaluator(probed_details_doc, namespaces=tag_nsmap)
    evaluator = partial(try_match_xpath, doc=evaluator, logger=logger)
    tags_defined = ((tag, tag.definition) for tag in tags if tag.is_defined)
    tags_matching, tags_nonmatching = classify(evaluator, tags_defined)
    node.tags.remove(*tags_nonmatching)
    node.tags.add(*tags_matching)
