# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handler: `CommissioningResult`."""

__all__ = [
    'NodeResultsHandler',
    ]

from maasserver.api.support import (
    operation,
    OperationsHandler,
)
from maasserver.api.utils import (
    get_optional_list,
    get_optional_param,
)
from maasserver.enum import NODE_PERMISSION
from maasserver.models import Node
from metadataserver.models import NodeResult


class NodeResultsHandler(OperationsHandler):
    """Read the collection of NodeResult in the MAAS."""
    api_doc_section_name = "Commissioning results"
    create = read = update = delete = None

    model = NodeResult
    fields = (
        'name', 'script_result', 'result_type', 'updated', 'created',
        'node', 'data')

    @operation(idempotent=True)
    def list(self, request):
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
        result_type = get_optional_param(request.GET, 'result_type')
        nodes = Node.objects.get_nodes(
            request.user, NODE_PERMISSION.VIEW, ids=system_ids)
        results = NodeResult.objects.filter(node_id__in=nodes)
        if names is not None:
            results = results.filter(name__in=names)
        if result_type is not None:
            results = results.filter(result_type__in=result_type)
        return results

    @classmethod
    def resource_uri(cls, result=None):
        return ('node_results_handler', [])
