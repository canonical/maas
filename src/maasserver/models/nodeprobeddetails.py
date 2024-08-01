# Copyright 2013-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Facilities to obtain probed details for nodes.

For example, hardware information as reported by ``lshw`` and network
topology information derived from LLDP.
"""

__all__ = [
    "get_probed_details",
    "get_single_probed_details",
    "script_output_nsmap",
]
import base64

from django.db import connection

from maasserver.models import Node
from metadataserver.enum import SCRIPT_STATUS
from provisioningserver.refresh.node_info_scripts import (
    LLDP_OUTPUT_NAME,
    LSHW_OUTPUT_NAME,
)

# A map of commissioning script output names to their detail
# namespaces. These namespaces are used in the return values from
# get_single_probed_details() and get_probed_details(), and in the
# composite XML document that's used when evaluating tag expressions.
script_output_nsmap = {LLDP_OUTPUT_NAME: "lldp", LSHW_OUTPUT_NAME: "lshw"}


def get_single_probed_details(node):
    """Return details of the node.

    Currently this consists of the node's ``lshw`` XML dump and an
    LLDP XML capture done during commissioning, but may be
    extended in the future.

    :return: A `dict` of the form ``{"lshw": b"<.../>", "lldp":
        b"<.../>"}``, where values are byte strings of XML.
    """
    details_template = dict.fromkeys(script_output_nsmap.values())
    script_set = node.current_commissioning_script_set
    if script_set is not None:
        # ScriptName only works here because LLDP and LSHW are builtin scripts
        # which are not stored in the Script table.
        for script_result in script_set.scriptresult_set.filter(
            status=SCRIPT_STATUS.PASSED, script_name__in=script_output_nsmap
        ).only(
            "status", "script_name", "stdout", "script_id", "script_set_id"
        ):
            namespace = script_output_nsmap[script_result.name]
            details_template[namespace] = script_result.stdout
    return details_template


def get_probed_details(nodes: list[Node]) -> dict[str, dict[str, str]]:
    """Return details of the nodes in the given list.

    :return: A ``{system_id: {...details...}, ...}`` map, where the
        inner dictionaries have the same form as those returned by
        `get_single_probed_details`.
    """
    node_ids = {node.id: node for node in nodes}
    ret = {
        node.system_id: dict.fromkeys(script_output_nsmap.values())
        for node in nodes
    }
    with connection.cursor() as cursor:
        # ScriptName only works here because LLDP and LSHW are builtin scripts
        # which are not stored in the Script table.
        sql_query = """
            SELECT
              script_set.node_id, script_result.script_name,
              script_result.stdout
            FROM
              maasserver_scriptresult AS script_result,
              maasserver_scriptset AS script_set,
              maasserver_node AS node
            WHERE
              script_set.node_id IN %s AND
              script_set.id = script_result.script_set_id AND
              script_result.status = %s AND
              script_result.script_name IN %s AND
              script_set.id = node.current_commissioning_script_set_id;
        """
        cursor.execute(
            sql_query,
            [
                tuple(node_ids),
                SCRIPT_STATUS.PASSED,
                tuple(script_output_nsmap),
            ],
        )
        for node_id, script_name, stdout in cursor.fetchall():
            system_id = node_ids[node_id].system_id
            namespace = script_output_nsmap[script_name]
            stdout_decoded = base64.b64decode(stdout)
            ret[system_id][namespace] = stdout_decoded
    return ret
