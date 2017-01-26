# Copyright 2014-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handler: `CommissioningResult`."""

__all__ = [
    'NodeResultsHandler',
    ]

from formencode.validators import Int
from maasserver.api.support import OperationsHandler
from maasserver.api.utils import (
    get_optional_list,
    get_optional_param,
)
from maasserver.enum import NODE_PERMISSION
from maasserver.models import Node
from metadataserver.models import ScriptResult


class NodeResultsHandler(OperationsHandler):
    """Read the collection of NodeResult in the MAAS."""
    api_doc_section_name = "Commissioning results"
    create = update = delete = None

    model = ScriptResult
    fields = (
        'name', 'script_result', 'result_type', 'updated', 'created',
        'node', 'data')

    def read(self, request):
        """List NodeResult visible to the user, optionally filtered.

        :param system_id: An optional list of system ids.  Only the
            results related to the nodes with these system ids
            will be returned.
        :type system_id: iterable
        :param name: An optional list of names.  Only the results
            with the specified names will be returned.
        :type name: iterable
        :param result_type: An optional result_type.  Only the results
            with the specified result_type will be returned.
        :type name: iterable
        """
        # Get filters from request.
        system_ids = get_optional_list(request.GET, 'system_id')
        names = get_optional_list(request.GET, 'name')
        result_type = get_optional_param(
            request.GET, 'result_type', None, Int)
        nodes = Node.objects.get_nodes(
            request.user, NODE_PERMISSION.VIEW, ids=system_ids)
        script_sets = []
        for node in nodes:
            if node.current_commissioning_script_set is not None:
                script_sets.append(node.current_commissioning_script_set)
            if node.current_installation_script_set is not None:
                script_sets.append(node.current_installation_script_set)
            if node.current_testing_script_set is not None:
                script_sets.append(node.current_testing_script_set)

        if names is not None:
            # Convert to a set; it's used for membership testing.
            names = set(names)

        results = []
        for script_set in script_sets:
            if (result_type is not None and
                    script_set.result_type != result_type):
                continue
            for script_result in script_set:
                if names is not None and script_result.name not in names:
                    continue
                results.append({
                    'created': script_result.created,
                    'updated': script_result.updated,
                    'id': script_result.id,
                    'name': script_result.name,
                    'script_result': script_result.exit_status,
                    'result_type': script_set.result_type,
                    'node': {'system_id': script_set.node.system_id},
                    'data': script_result.stdout.decode('utf-8'),
                })
                if script_result.stderr != b'':
                    results.append({
                        'created': script_result.created,
                        'updated': script_result.updated,
                        'id': script_result.id,
                        'name': '%s.err' % script_result.name,
                        'script_result': script_result.exit_status,
                        'result_type': script_set.result_type,
                        'node': {'system_id': script_set.node.system_id},
                        'data': script_result.stderr.decode('utf-8'),
                    })

        return results

    @classmethod
    def resource_uri(cls, result=None):
        return ('node_results_handler', [])
