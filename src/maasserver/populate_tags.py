# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Populate what nodes are associated with a tag."""

from __future__ import annotations

__all__ = [
    "populate_tag_for_multiple_nodes",
    "populate_tags_for_single_node",
]

from functools import partial
from typing import TYPE_CHECKING

from django.db.models.query import QuerySet
from lxml import etree

from maasserver import logger
from maasserver.models.node import Node
from maasserver.models.nodeprobeddetails import (
    get_probed_details,
    get_single_probed_details,
    script_output_nsmap,
)
from provisioningserver.logger import get_maas_logger, LegacyLogger
from provisioningserver.tags import (
    DEFAULT_BATCH_SIZE,
    gen_batches,
    merge_details,
)
from provisioningserver.utils import classify
from provisioningserver.utils.twisted import synchronous
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
    tag: Tag, nodes: QuerySet[Node], batch_size: int = DEFAULT_BATCH_SIZE
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
