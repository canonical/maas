# Copyright 2012 Canonical Ltd.  This software is licensed under the
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

from lxml import etree
from maasserver import logger
from maasserver.models import NodeGroup
from maasserver.models.nodeprobeddetails import (
    get_single_probed_details,
    script_output_nsmap,
    )
from maasserver.refresh_worker import refresh_worker
from provisioningserver.tags import merge_details
from provisioningserver.tasks import update_node_tags
from provisioningserver.utils import (
    classify,
    try_match_xpath,
    )

# The nsmap that XPath expression must be compiled with. This will
# ensure that expressions like //lshw:something will work correctly.
tag_nsmap = {
    namespace: namespace
    for namespace in script_output_nsmap.itervalues()
}


def populate_tags(tag):
    """Send worker for all nodegroups an update_node_tags request.
    """
    items = {
        'tag_name': tag.name,
        'tag_definition': tag.definition,
        'tag_nsmap': tag_nsmap,
    }
    # Rather than using NodeGroup.objects.refresh_workers() we call
    # refresh_worker immediately before we pass the requet. This is mostly for
    # the test suite, where we need the single real worker to switch to the
    # worker for a given nodegroup, before we have that worker process the
    # request.
    logger.debug('Refreshing tag definition for %s' % (items,))
    for nodegroup in NodeGroup.objects.all():
        refresh_worker(nodegroup)
        update_node_tags.apply_async(queue=nodegroup.work_queue, kwargs=items)


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
