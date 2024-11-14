# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Implementation of the tag evaluation workflow.

A tag is a label associated to one or more nodes. There are two types of tags:
- manual tags: tag associated manually to a node by the user.
- automatic tags: tag defined by the user and assigned automatically based on a
  certain criterion.

The tag evaluation workflow checks if the tag definition provided by the user
matches any node in MAAS. If the evaluation shows that there is match between
the tag and the node, the match is registered in the database.
If the user updates an automatic tag, changing the definition, the workflow is
triggered, validating the tag against all nodes like it would do when a new one
is created. The tag-node relation can then be created, deleted or maintained as
it was.

The evaluation consists in matching the tag definition against the output of
some scripts that run during the node commissioning phase. The output of those
scripts is expected to be in XML format, and the tag definition to be a XPath
expression.
"""

from dataclasses import dataclass
from datetime import timedelta
from functools import reduce

from sqlalchemy import text
import structlog
from temporalio import workflow
from temporalio.common import RetryPolicy

from maascommon.workflows.tag import (
    TAG_EVALUATION_WORKFLOW_NAME,
    TagEvaluationParam,
)
from maastemporalworker.workflow.activity import ActivityBase
from maastemporalworker.workflow.utils import (
    activity_defn_with_context,
    workflow_run_with_context,
)
from metadataserver.enum import SCRIPT_STATUS
from provisioningserver.refresh.node_info_scripts import (
    LLDP_OUTPUT_NAME,
    LSHW_OUTPUT_NAME,
)

logger = structlog.getLogger()


TAG_EVALUATION_ACTIVITY_TIMEOUT = timedelta(minutes=10)

# Activities names
EVALUATE_TAG_ACTIVITY_NAME = "evaluate-tag"


# Activities parameters
@dataclass(frozen=True)
class TagEvaluationResult:
    inserted: int
    deleted: int


@workflow.defn(name=TAG_EVALUATION_WORKFLOW_NAME, sandboxed=False)
class TagEvaluationWorkflow:
    """Temporal workflow for tag evaluation."""

    @workflow_run_with_context
    async def run(self, param: TagEvaluationParam) -> None:
        logger.info(f"Tag (id={param.tag_id}) evaluation starts.")
        result: TagEvaluationResult = await workflow.execute_activity(
            TagEvaluationActivity.evaluate_tag,
            arg=param,
            retry_policy=RetryPolicy(maximum_attempts=3),
            start_to_close_timeout=TAG_EVALUATION_ACTIVITY_TIMEOUT,
        )
        logger.info(
            f"Tag (id={param.tag_id}) evaluation ends: {result.inserted} nodes were tagged and {result.deleted} nodes were untagged"
        )


class TagEvaluationActivity(ActivityBase):
    """Temporal activity for tag evaluation."""

    @activity_defn_with_context(name=EVALUATE_TAG_ACTIVITY_NAME)
    async def evaluate_tag(
        self, param: TagEvaluationParam
    ) -> TagEvaluationResult:
        """
        Run the tag evaluation activity as Temporal activity.

        The activity takes a tag definition (XPath expression), and runs it
        against the output of some of the scripts that capture information about
        the node. See LSHW_OUTPUT_NAME and LLDP_OUTPUT_NAME to identify those
        scripts.

        If there is a match, the node-tag relation is kept in the database.
        Otherwise, it is deleted if it was already stored (this can happen if a
        user edit the tag).

        * Batch processing
        Considering that the tag evaluation is not a critical process in MAAS,
        we would like to avoid that this activity keeps a database transaction
        open for too long. In that way, critical processes can make a better use
        of a limited number of transactions.
        See TAG_EVALUATION_BATCH_SIZE definition for more information.
        """
        processed_nodes = param.batch_size
        outputs = [{"inserted": 0, "deleted": 0}]
        pointer = -1

        while 0 < param.batch_size == processed_nodes:

            async with self._start_transaction() as tx:
                stmt = f"""
WITH batch_nodes_cte AS (
    /* retrieve the batch of nodes to be processed
       The pagination is done by providing the first node ID of the batch
       (pointer) and the batch size.
    */
    SELECT
        id
    FROM maasserver_node
    WHERE id > {pointer}
    ORDER BY id
    LIMIT {param.batch_size}
),
batch_nodes_to_be_evaluated_cte AS (
    /* retrieve the nodes that:
       - ran the LSHW_OUTPUT_NAME, LLDP_OUTPUT_NAME scripts successfully in
         their last commissioning script set
       - have a well formed script output for the LSHW_OUTPUT_NAME,
         LLDP_OUTPUT_NAME scripts
    */
    SELECT
        mss.node_id
        , msr.script_name
        , msr.stdout
    FROM
        maasserver_node mn
    INNER JOIN maasserver_scriptset mss
        ON mn.id = mss.node_id
    INNER JOIN maasserver_scriptresult msr
        ON mss.id = msr.script_set_id
    WHERE 1=1
        AND mss.node_id IN (select id from batch_nodes_cte)
        AND mss.id = mn.current_commissioning_script_set_id
        AND msr.status = {SCRIPT_STATUS.PASSED}
        AND msr.script_name IN {LSHW_OUTPUT_NAME, LLDP_OUTPUT_NAME}
        AND xml_is_well_formed_document(
            CONVERT_FROM(
                DECODE(msr.stdout, 'base64'),
                'UTF8'
            )::text
        )
    GROUP BY
        mss.node_id
        , msr.script_name
        , msr.stdout
),
node_tag_match_cte AS (
    /* provides the results of the tag evaluation:
       - node_id: node being evaluated
       - tag_id: tag used in the evaluation
       - matched: boolean with the result of the tag evaluation.
           true if there is a node-tag match
           false if there is not a node-tag match
    */
    SELECT
        node_id
        , {param.tag_id} AS tag_id
        , BOOL_OR(
            XPATH_EXISTS(
                '{param.tag_definition}',
                CONVERT_FROM(
                    DECODE(stdout, 'base64'),
                    'UTF8'
                )::xml
            )
        ) AS matched
    FROM batch_nodes_to_be_evaluated_cte
    GROUP BY
        node_id
),
node_tag_action_cte AS (
    /* given the node-tag matching information, this CTE provides the action to
      take for each node-tag pair. This can be:
      - insert: new node-tag entry must be created because there is a match for
        that pair and it has been stored in the database yet
      - delete: node-tag entry must be deleted because the node-tag pair does
        not match anymore
      - none: either there is a node-tag matching, but is already registered or
        there is no node-tag matching and the relation is not registered.
    */
    SELECT
        ntmc.node_id
        , ntmc.tag_id
        , CASE
            WHEN
                (mnt.node_id IS NULL OR mnt.tag_id IS NULL) AND matched
                THEN 'insert'
            WHEN
                (mnt.node_id IS NOT NULL AND mnt.tag_id IS NOT NULL)
                AND NOT matched
                THEN 'delete'
            ELSE 'none'
        END AS action
    from node_tag_match_cte ntmc
    left join maasserver_node_tags mnt
        on ntmc.node_id = mnt.node_id
        and ntmc.tag_id = mnt.tag_id
),
delete_rows_cte AS (
    /* delete the tag-node pairs marked for deletion, returning the node-tag
       pairs that have been deleted
    */
    DELETE FROM maasserver_node_tags
    WHERE (node_id, tag_id, 'delete')
        IN (SELECT node_id, tag_id, action FROM node_tag_action_cte)
    RETURNING node_id, tag_id
),
insert_rows_cte AS (
    /* insert the tag-node pairs marked for insertion, returning the node-tag
       pairs that have been inserted
    */
    INSERT INTO maasserver_node_tags (node_id, tag_id)
        SELECT node_id , tag_id
        FROM node_tag_action_cte WHERE action = 'insert'
    RETURNING node_id, tag_id
)
SELECT 'deleted', count(1) FROM delete_rows_cte
UNION
SELECT 'inserted', count(1) FROM insert_rows_cte
UNION
SELECT 'processed', COALESCE(count(id), 0) FROM batch_nodes_cte
UNION
SELECT 'pointer', max(id) FROM batch_nodes_cte
;
                """
                cursor_result = await tx.execute(text(stmt))
                output = {k: v for k, v in cursor_result.all()}

                processed_nodes = output.pop("processed")
                pointer = output.pop("pointer")
                outputs.append(output)

        result = TagEvaluationResult(
            **reduce(
                lambda a, b: {k: a[k] + b[k] for k in a.keys()},
                outputs,
            )
        )

        return result
