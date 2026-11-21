# Copyright 2013-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.models.nodeprobeddetails`."""

from maasserver.models.nodeprobeddetails import (
    get_probed_details,
    get_single_probed_details,
    script_output_nsmap,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from metadataserver.enum import RESULT_TYPE, SCRIPT_STATUS
from provisioningserver.refresh.node_info_scripts import (
    LLDP_OUTPUT_NAME,
    LSHW_OUTPUT_NAME,
)


class TestNodeDetail(MAASServerTestCase):
    def make_script_set_and_results(self, node, suffix="data"):
        script_set = factory.make_ScriptSet(
            node=node, result_type=RESULT_TYPE.COMMISSIONING
        )
        return (
            script_set,
            [
                factory.make_ScriptResult(
                    script_set=script_set,
                    script_name=LSHW_OUTPUT_NAME,
                    exit_status=0,
                    status=SCRIPT_STATUS.PASSED,
                    stdout=b"<lshw-%s/>" % suffix.encode(),
                ),
                factory.make_ScriptResult(
                    script_set=script_set,
                    script_name=LLDP_OUTPUT_NAME,
                    exit_status=0,
                    status=SCRIPT_STATUS.PASSED,
                    stdout=b"<lldp-%s/>" % suffix.encode(),
                ),
            ],
        )

    def test_returns_all_details(self):
        node = factory.make_Node(with_empty_script_sets=True)
        script_set = node.current_commissioning_script_set
        for script_name, stdout in (
            (LSHW_OUTPUT_NAME, b"<lshw-data/>"),
            (LLDP_OUTPUT_NAME, b"<lldp-data/>"),
        ):
            script_result = script_set.find_script_result(
                script_name=script_name
            )
            script_result.store_result(exit_status=0, stdout=stdout)
        self.assertDictEqual(
            {"lshw": b"<lshw-data/>", "lldp": b"<lldp-data/>"},
            get_single_probed_details(node),
        )

    def test_returns_null_details_when_there_are_none(self):
        node = factory.make_Node()
        self.assertDictEqual(
            {"lshw": None, "lldp": None}, get_single_probed_details(node)
        )

    def test_returns_only_details_from_okay_commissioning_results(self):
        node = factory.make_Node(with_empty_script_sets=True)
        script_set = node.current_commissioning_script_set
        for script_name, stdout, exit_status in (
            (LSHW_OUTPUT_NAME, b"<lshw-data/>", 0),
            (LLDP_OUTPUT_NAME, b"<lldp-data/>", 1),
        ):
            script_result = script_set.find_script_result(
                script_name=script_name
            )
            script_result.store_result(exit_status=exit_status, stdout=stdout)
        self.assertDictEqual(
            {"lshw": b"<lshw-data/>", "lldp": None},
            get_single_probed_details(node),
        )

    def test_get_probed_details(self):
        expected = {}
        nodes = [factory.make_Node() for _ in range(3)]
        for node in nodes:
            # Create some old results. These will _not_ be returned by
            # get probed_details.
            self.make_script_set_and_results(node, "old")
            # Create the current results. These will be returned by
            # get_probed_details.
            script_set, script_results = self.make_script_set_and_results(node)
            node.current_commissioning_script_set = script_set
            node.save()
            expected[node.system_id] = {
                script_output_nsmap[result.script_name]: result.stdout
                for result in script_results
            }
            # Create some new but not current results. These will _not_ be
            # returned by get_probed_details.
            self.make_script_set_and_results(node, "new")
        self.assertDictEqual(expected, get_probed_details(nodes))
