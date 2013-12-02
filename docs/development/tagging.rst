.. -*- mode: rst -*-

*******
Tagging
*******


Auto tags, or tags with expressions
===================================

These kind of tags have an associated XPath expression that is
evaluated against hardware information as obtained from running
``lshw`` during node commissioning.


New or updated tag definition
-----------------------------

When a new tag is created or an existing tag is modified, its
expression must be evaluated for every node known to the region. It's
a moderately computationally intensive process, so the work is spread
out to cluster controllers. Here's how:

#. The region dispatches a
   ``provisioningserver.tasks.update_node_tags`` job to each cluster
   for each tag it wants evaluated.

   It sends the tag name and its definition, an XPath expression.

   See ``maasserver.model.tags.Tag.save`` and
   ``maasserver.populate_tags``.

#. The task is run (by Celery) on each cluster. This calls
   ``provisioningserver.tags.process_node_tags``.

#. The system IDs for all nodes in that cluster (aka node group) are
   fetched by calling back to the region.

   See ``provisioningserver.tags.get_nodes_for_node_group``.

#. Nodes are then processed in batches. For each batch:

   #. Hardware details are obtained from the region for the batch as a
      whole.

      See ``provisioningserver.tags.get_hardware_details_for_nodes``.

   #. The tag expression is evaluated against each node's hardware
      details. The result of the expression, cast as a boolean,
      determines if the tag applies to this node.

      See ``provisioningserver.tags.process_batch``.

   #. The results are sent back to the region for the batch as a
      whole.

      See ``provisioningserver.tags.post_updated_nodes``.


New or updated commissioning result
-----------------------------------

When a new commissioning result comes in containing ``lshw`` or ``lldp``
XML output, every tag with an expression must be evaluated against the
result so that the node is correctly tagged.

To do this, ``maasserver.api.VersionIndexHandler.signal`` calls
``populate_tags_for_single_node`` just before saving all the changes.
This happens in the **region**. While it's a computationally expensive
operation, the overhead of spinning this work out to a cluster
controller negates any benefit that might gained by doing so.


Manual tags, or tags without expressions
========================================

The *manual* part refers to how these tags are associated with nodes.
Instead of being automatically associated as the result of evaluating
the tag expression, these tags must be manually associated with a
node. A manual tag is denoted by the absence of an expression.
