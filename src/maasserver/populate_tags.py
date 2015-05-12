# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Populate what nodes are associated with a tag."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'populate_tags',
    'populate_tags_for_single_node',
    ]

from functools import partial
from itertools import izip

from lxml import etree
from maasserver import logger
from maasserver.models import NodeGroup
from maasserver.models.nodeprobeddetails import (
    get_single_probed_details,
    script_output_nsmap,
)
from maasserver.rpc import getClientFor
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
    logger.debug('Evaluating the "%s" tag for all nodes', tag.name)
    clusters = tuple(
        (nodegroup.uuid, nodegroup.cluster_name, nodegroup.api_credentials)
        for nodegroup in NodeGroup.objects.all_accepted())
    [d] = _do_populate_tags(clusters, tag.name, tag.definition, tag_nsmap)
    return d


@asynchronous(timeout=FOREVER)
def _do_populate_tags(clusters, tag_name, tag_definition, tag_nsmap):
    """Send RPC calls to each cluster, requesting evaluation of tags.

    :param clusters: A sequence of ``(uuid, cluster-name, creds)`` tuples for
        each cluster. The name is used for logging only.
    :param tag_name: The name of the tag being evaluated.
    :param tag_definition: The definition of the tag, an XPath expression.
    :oaram tag_nsmap: The NS mapping used to compile the expression.
    """
    creds = {uuid: creds for uuid, _, creds in clusters}
    tag_nsmap_on_wire = [
        {"prefix": prefix, "uri": uri}
        for prefix, uri in tag_nsmap.viewitems()
    ]

    def make_call(client):
        return client(
            EvaluateTag, tag_name=tag_name, tag_definition=tag_definition,
            tag_nsmap=tag_nsmap_on_wire, credentials=creds[client.ident])

    def evaluate_tags(clients):
        # Call EvaluateTag on each cluster concurrently.
        return DeferredList(
            (make_call(client) for client in clients),
            consumeErrors=True)

    def check_results(results):
        for (uuid, name, creds), (success, result) in izip(clusters, results):
            if success:
                maaslog.info(
                    "Tag %s (%s) evaluated on cluster %s (%s)", tag_name,
                    tag_definition, name, uuid)
            else:
                maaslog.error(
                    "Tag %s (%s) could not be evaluated on cluster %s (%s): "
                    "%s", tag_name, tag_definition, name, uuid,
                    result.getErrorMessage())

    d = _get_clients_for_populating_tags(
        [(uuid, name) for (uuid, name, _) in clusters], tag_name)
    d.addCallback(evaluate_tags)
    d.addCallback(check_results)
    d.addErrback(log.err)

    # Do *not* return a Deferred; the caller is not meant to wait around for
    # this to finish. However, for the sake of testing, we return the Deferred
    # wrapped up in a list so that crochet does not block.
    return [d]


@asynchronous(timeout=FOREVER)
def _get_clients_for_populating_tags(clusters, tag_name):
    """Obtain RPC clients for the given clusters.

    :param clusters: A sequence of ``(uuid, name)`` tuples for each cluster.
        The name is used for logging only.
    :param tag_name: The tag for which these clients are being obtained. This
        is used only for logging.
    """
    # Wait up to `timeout` seconds to obtain clients to all clusters.
    d = DeferredList(
        (getClientFor(uuid, timeout=30) for uuid, _ in clusters),
        consumeErrors=True)

    def got_clients(results):
        clients = []
        for (uuid, name), (success, result) in izip(clusters, results):
            if success:
                clients.append(result)
            else:
                # XXX: allenap 2014-09-22 bug=1372544: Filtering out
                # unavailable (or otherwise broken) clients means that tags
                # aren't going to be evaluated for that cluster's nodes.
                # That's bad. It would be good to be able to ask another
                # cluster to evaluate them, but the cluster-side code needs
                # changing to allow that. For now, we just skip.
                maaslog.warning(
                    "Cannot evaluate tag %s on cluster %s (%s): %s",
                    tag_name, name, uuid, result.getErrorMessage())
        return clients

    return d.addCallback(got_clients)


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
