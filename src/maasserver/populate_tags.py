# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Populate what nodes are associated with a tag."""

from __future__ import annotations

__all__ = [
    "populate_tag_for_multiple_nodes",
    "populate_tags",
    "populate_tags_for_single_node",
]

from functools import partial
from math import ceil
from typing import TYPE_CHECKING

from django.db.models.query import QuerySet
from django.db.transaction import TransactionManagementError
from lxml import etree
from twisted.internet.defer import DeferredList

from apiclient.creds import convert_tuple_to_string
from maasserver import logger
from maasserver.models.node import Node, RackController
from maasserver.models.nodeprobeddetails import (
    get_probed_details,
    get_single_probed_details,
    script_output_nsmap,
)
from maasserver.models.user import (
    create_auth_token,
    get_auth_tokens,
    get_creds_tuple,
)
from maasserver.rpc import getAllClients
from maasserver.utils.orm import in_transaction, transactional
from provisioningserver.logger import get_maas_logger, LegacyLogger
from provisioningserver.rpc.cluster import EvaluateTag
from provisioningserver.tags import (
    DEFAULT_BATCH_SIZE,
    gen_batches,
    merge_details,
)
from provisioningserver.utils import classify
from provisioningserver.utils.twisted import asynchronous, FOREVER, synchronous
from provisioningserver.utils.xpath import try_match_xpath

if TYPE_CHECKING:
    from maasserver.models import Tag

maaslog = get_maas_logger("tags")
log = LegacyLogger()


# The nsmap that XPath expression must be compiled with. This will
# ensure that expressions like //lshw:something will work correctly.
tag_nsmap = {
    namespace: namespace for namespace in script_output_nsmap.values()
}


def chunk_list(items, num_chunks):
    """Split `items` into (at most) `num_chunks` lists.

    Every chunk will have at least one element in its list, which may
    mean that we don't actually get as many chunks as the user asked
    for.  The final chunk (of how ever many we create) is likely to be
    smaller than the rest, since we always round up to the nearest
    integer for chunk size.
    """
    size = ceil(len(items) / num_chunks)
    for i in range(0, len(items), size):
        yield items[i : i + size]


@synchronous
def populate_tags(tag: Tag):
    """Evaluate `tag` for all nodes.

    This returns a `Deferred` that will fire when all tags have been
    evaluated. The return value is intended FOR TESTING ONLY because:

    - You must not use the `Deferred` in the calling thread; it must only be
      manipulated in the reactor thread. Pretending it's not there is safer
      than chaining code onto it because it's easy to get wrong.

    - The call may not finish for 10 minutes or more. It is therefore not a
      good thing to be waiting for in a web request.

    """
    # This function cannot be called inside a transaction. The function manages
    # its own transaction.
    if in_transaction():
        raise TransactionManagementError(
            "`populate_tags` cannot be called inside an existing transaction."
        )

    logger.debug('Evaluating the "%s" tag for all nodes.', tag.name)

    clients = getAllClients()
    if len(clients) == 0:
        # We have no clients, so we need to do the work locally.
        @transactional
        def _populate_tag():
            return populate_tag_for_multiple_nodes(tag, Node.objects.all())

        return _populate_tag()
    else:
        # Split the work between the connected rack controllers.
        @transactional
        def _generate_work() -> list[dict]:
            node_ids = Node.objects.all().values_list("system_id", flat=True)
            node_ids = [{"system_id": node_id} for node_id in node_ids]
            chunked_node_ids = list(chunk_list(node_ids, len(clients)))
            connected_racks = []
            for idx, client in enumerate(clients):
                rack = RackController.objects.get(system_id=client.ident)
                token = _get_or_create_auth_token(rack.owner)
                creds = convert_tuple_to_string(get_creds_tuple(token))
                if len(chunked_node_ids) > idx:
                    connected_racks.append(
                        {
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
                        }
                    )
            return connected_racks

        return _do_populate_tags(_generate_work())


def _get_or_create_auth_token(user):
    """Get the most recent OAuth token for `user`, or create one."""
    for token in reversed(get_auth_tokens(user)):
        return token
    else:
        return create_auth_token(user)


@asynchronous(timeout=FOREVER)
def _do_populate_tags(clients: list[dict]) -> list[DeferredList]:
    """Send RPC calls to each rack controller, requesting evaluation of tags.

    :param clients: List of connected rack controllers that EvaluateTag
        will be called.
    """

    def call_client(client_info: dict):
        client = client_info["client"]
        return client(
            EvaluateTag,
            system_id=client_info["system_id"],
            tag_name=client_info["tag_name"],
            tag_definition=client_info["tag_definition"],
            tag_nsmap=client_info["tag_nsmap"],
            credentials=client_info["credentials"],
            nodes=client_info["nodes"],
        )

    def check_results(results):
        for client_info, (success, result) in zip(clients, results):
            if success:
                maaslog.info(
                    "Tag %s (%s) evaluated on rack controller %s (%s)",
                    client_info["tag_name"],
                    client_info["tag_definition"],
                    client_info["hostname"],
                    client_info["system_id"],
                )
            else:
                maaslog.error(
                    "Tag %s (%s) could not be evaluated on rack controller "
                    "%s (%s): %s",
                    client_info["tag_name"],
                    client_info["tag_definition"],
                    client_info["hostname"],
                    client_info["system_id"],
                    result.getErrorMessage(),
                )

    d = DeferredList(
        (call_client(client_info) for client_info in clients),
        consumeErrors=True,
    )
    d.addCallback(check_results)
    d.addErrback(log.err)

    # Do *not* return a Deferred; the caller is not meant to wait around for
    # this to finish. However, for the sake of testing, we return the Deferred
    # wrapped up in a list so that crochet does not block.
    return [d]


@synchronous
def populate_tags_for_single_node(tags, node):
    """Reevaluate all tags for a single node.

    Presumably this node's details have recently changed. Use `populate_tags`
    when many nodes need reevaluating AND there are rack controllers available
    to which to farm-out work. Use `populate_tag_for_multiple_nodes` when many
    nodes need reevaluating locally, i.e. when there are no rack controllers
    connected.
    """
    probed_details = get_single_probed_details(node)
    probed_details_doc = merge_details(probed_details)
    # Same document, many queries: use XPathEvaluator.
    evaluator = etree.XPathEvaluator(probed_details_doc, namespaces=tag_nsmap)
    evaluator = partial(try_match_xpath, doc=evaluator, logger=logger)
    tags_defined = ((tag, tag.definition) for tag in tags if tag.is_defined)
    tags_matching, tags_nonmatching = classify(evaluator, tags_defined)
    node.tags.remove(*tags_nonmatching)
    node.tags.add(*tags_matching)


@synchronous
def populate_tag_for_multiple_nodes(
    tag: Tag, nodes: QuerySet, batch_size: int = DEFAULT_BATCH_SIZE
) -> None:
    """Reevaluate a single tag for multiple nodes.

    Presumably this tag's expression has recently changed. Use `populate_tags`
    when many nodes need reevaluating AND there are rack controllers available
    to which to farm-out work. Use this only when many nodes need reevaluating
    locally, i.e. when there are no rack controllers connected.
    """
    # Same expression, multiple documents: compile expression with XPath.
    xpath = etree.XPath(tag.definition, namespaces=tag_nsmap)
    # The XML details documents can be large so work in batches.
    for batch in gen_batches(nodes, batch_size):
        probed_details = get_probed_details(batch)
        probed_details_docs_by_node = {
            node: merge_details(probed_details[node.system_id])
            for node in batch
        }
        nodes_matching, nodes_nonmatching = classify(
            partial(try_match_xpath, xpath, logger=maaslog),
            probed_details_docs_by_node.items(),
        )
        tag.node_set.remove(*nodes_nonmatching)
        tag.node_set.add(*nodes_matching)
