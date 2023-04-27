# Copyright 2014-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handler: `CommissioningResult`."""


from base64 import b64encode

from django.urls import reverse
from formencode.validators import Int

from maasserver.api.support import OperationsHandler
from maasserver.api.utils import get_optional_list, get_optional_param
from maasserver.models import Node, ScriptResult
from maasserver.permissions import NodePermission
from metadataserver.enum import SCRIPT_STATUS


class NodeResultsHandler(OperationsHandler):
    """Read the collection of commissioning script results."""

    api_doc_section_name = "Commissioning results"
    create = update = delete = None

    model = ScriptResult
    fields = (
        "name",
        "script_result",
        "result_type",
        "updated",
        "created",
        "node",
        "data",
        "resource_uri",
    )

    def read(self, request):
        """@description-title Read commissioning results
        @description Read the commissioning results per node visible to the
        user, optionally filtered.

        @param (string) "system_id" [required=false] An optional list of system
        ids. Only the results related to the nodes with these system ids will
        be returned.

        @param (string) "name" [required=false] An optional list of names.
        Only the results with the specified names will be returned.

        @param (string) "result_type" [required=false] An optional result_type.
        Only the results with the specified result_type will be returned.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of the
        requested installation-result objects.
        @success-example "success-json" [exkey=installation-results]
        placeholder text
        """
        # Get filters from request.
        system_ids = get_optional_list(request.GET, "system_id")
        names = get_optional_list(request.GET, "name")
        result_type = get_optional_param(request.GET, "result_type", None, Int)
        nodes = Node.objects.get_nodes(
            request.user, NodePermission.view, ids=system_ids
        )
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

        resource_uri = reverse("commissioning_scripts_handler")

        results = []
        for script_set in script_sets:
            if (
                result_type is not None
                and script_set.result_type != result_type
            ):
                continue
            for script_result in script_set.scriptresult_set.filter(
                status__in=(
                    SCRIPT_STATUS.PASSED,
                    SCRIPT_STATUS.FAILED,
                    SCRIPT_STATUS.TIMEDOUT,
                    SCRIPT_STATUS.ABORTED,
                )
            ):
                if names is not None and script_result.name not in names:
                    continue
                # MAAS stores stdout, stderr, and the combined output. The
                # metadata API determine which field uploaded data should go
                # into based on the extention of the uploaded file. .out goes
                # to stdout, .err goes to stderr, otherwise its assumed the
                # data is combined. Curtin uploads the installation log as
                # install.log so its stored as a combined result. This ensures
                # a result is always returned.
                if script_result.stdout != b"":
                    data = b64encode(script_result.stdout)
                else:
                    data = b64encode(script_result.output)
                results.append(
                    {
                        "created": script_result.created,
                        "updated": script_result.updated,
                        "id": script_result.id,
                        "name": script_result.name,
                        "script_result": script_result.exit_status,
                        "result_type": script_set.result_type,
                        "node": {"system_id": script_set.node.system_id},
                        "data": data,
                        "resource_uri": resource_uri,
                    }
                )
                if script_result.stderr != b"":
                    results.append(
                        {
                            "created": script_result.created,
                            "updated": script_result.updated,
                            "id": script_result.id,
                            "name": "%s.err" % script_result.name,
                            "script_result": script_result.exit_status,
                            "result_type": script_set.result_type,
                            "node": {"system_id": script_set.node.system_id},
                            "data": b64encode(script_result.stderr),
                            "resource_uri": resource_uri,
                        }
                    )

        return results

    @classmethod
    def resource_uri(cls, result=None):
        return ("node_results_handler", [])
