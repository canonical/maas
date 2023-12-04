# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for tag updating."""


from functools import partial
import http.client
from itertools import chain
import json
from textwrap import dedent
from unittest.mock import call, MagicMock, sentinel
import urllib.error
import urllib.parse
import urllib.request

import bson
from fixtures import FakeLogger
from lxml import etree

from apiclient.maas_client import MAASClient
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver import tags
from provisioningserver.testing.config import ClusterConfigurationFixture


class TestProcessResponse(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.useFixture(FakeLogger())

    def test_process_OK_response_with_JSON_content(self):
        data = {"abc": 123}
        response = factory.make_response(
            http.client.OK,
            json.dumps(data).encode("ascii"),
            "application/json",
        )
        self.assertEqual(data, tags.process_response(response))

    def test_process_OK_response_with_BSON_content(self):
        data = {"abc": 123}
        response = factory.make_response(
            http.client.OK, bson.BSON.encode(data), "application/bson"
        )
        self.assertEqual(data, tags.process_response(response))

    def test_process_OK_response_with_other_content(self):
        data = factory.make_bytes()
        response = factory.make_response(
            http.client.OK, data, "application/octet-stream"
        )
        self.assertEqual(data, tags.process_response(response))

    def test_process_not_OK_response(self):
        response = factory.make_response(
            http.client.NOT_FOUND, b"", "application/json"
        )
        response.url = factory.make_string()
        error = self.assertRaises(
            urllib.error.HTTPError, tags.process_response, response
        )
        self.assertEqual(error.url, response.url)
        self.assertEqual(error.code, response.code)
        self.assertEqual(error.msg, "Not Found, expected 200 OK")
        self.assertEqual(error.headers, response.headers)
        self.assertEqual(error.fp, response.fp)


class TestMergeDetailsCleanly(MAASTestCase):
    do_merge_details = staticmethod(tags.merge_details_cleanly)

    def setUp(self):
        super().setUp()
        self.logger = self.useFixture(FakeLogger("maas"))

    def assertXMLEqual(self, actual: etree.ElementTree, expected: str):
        normalise = partial(etree.tostring, pretty_print=True)
        n_actual = normalise(actual)
        n_expected = normalise(etree.fromstring(dedent(expected)))
        return self.assertEqual(n_actual, n_expected)

    def test_merge_with_no_details(self):
        xml = self.do_merge_details({})
        self.assertXMLEqual(xml, "<list/>")

    def test_merge_with_only_lshw_details(self):
        xml = self.do_merge_details({"lshw": b"<list><foo>Hello</foo></list>"})
        expected = """\
            <list xmlns:lshw="lshw">
              <lshw:list>
                <lshw:foo>Hello</lshw:foo>
              </lshw:list>
            </list>
        """
        self.assertXMLEqual(xml, expected)

    def test_merge_with_only_lldp_details(self):
        xml = self.do_merge_details({"lldp": b"<node><foo>Hello</foo></node>"})
        expected = """\
            <list xmlns:lldp="lldp">
              <lldp:node>
                <lldp:foo>Hello</lldp:foo>
              </lldp:node>
            </list>
        """
        self.assertXMLEqual(xml, expected)

    def test_merge_with_multiple_details(self):
        xml = self.do_merge_details(
            {
                "lshw": b"<list><foo>Hello</foo></list>",
                "lldp": b"<node><foo>Hello</foo></node>",
                "zoom": b"<zoom>zoom</zoom>",
            }
        )
        expected = """\
            <list xmlns:lldp="lldp" xmlns:lshw="lshw" xmlns:zoom="zoom">
              <lldp:node>
                <lldp:foo>Hello</lldp:foo>
              </lldp:node>
              <lshw:list>
                <lshw:foo>Hello</lshw:foo>
              </lshw:list>
              <zoom:zoom>zoom</zoom:zoom>
            </list>
        """
        self.assertXMLEqual(xml, expected)

    def test_merges_into_new_tree(self):
        xml = self.do_merge_details(
            {
                "lshw": b"<list><foo>Hello</foo></list>",
                "lldp": b"<node><foo>Hello</foo></node>",
            }
        )
        # The presence of a getroot() method indicates that this is a
        # tree object, not an element.
        self.assertTrue(callable(xml.getroot))
        # The list tag can be obtained using an XPath expression
        # starting from the root of the tree.
        self.assertEqual(["list"], [elem.tag for elem in xml.xpath("/list")])

    def test_merge_with_invalid_lshw_details(self):
        # The lshw details cannot be parsed, but merge_details_cleanly() still
        # returns a usable tree, albeit without any lshw details.
        xml = self.do_merge_details({"lshw": b"<not>well</formed>"})
        self.assertXMLEqual(xml, '<list xmlns:lshw="lshw"/>')
        # The error is logged however.
        self.assertIn("Invalid lshw details: ", self.logger.output)

    def test_merge_with_invalid_lshw_details_and_others_valid(self):
        # The lshw details cannot be parsed, but merge_details_cleanly() still
        # returns a usable tree, albeit without any lshw details.
        xml = self.do_merge_details(
            {
                "lshw": b"<not>well</formed>",
                "lldp": b"<node><foo>Hello</foo></node>",
                "zoom": b"<zoom>zoom</zoom>",
            }
        )
        expected = """\
            <list xmlns:lldp="lldp" xmlns:lshw="lshw" xmlns:zoom="zoom">
              <lldp:node>
                <lldp:foo>Hello</lldp:foo>
              </lldp:node>
              <zoom:zoom>zoom</zoom:zoom>
            </list>
        """
        self.assertXMLEqual(xml, expected)
        # The error is logged however.
        self.assertIn("Invalid lshw details: ", self.logger.output)

    def test_merge_with_invalid_other_details(self):
        xml = self.do_merge_details(
            {
                "lshw": b"<list><foo>Hello</foo></list>",
                "foom": b"<not>well</formed>",
                "zoom": b"<zoom>zoom</zoom>",
                "oops": None,
            }
        )
        expected = """\
            <list xmlns:foom="foom" xmlns:lshw="lshw"
                  xmlns:oops="oops" xmlns:zoom="zoom">
              <lshw:list>
                <lshw:foo>Hello</lshw:foo>
              </lshw:list>
              <zoom:zoom>zoom</zoom:zoom>
            </list>
        """
        self.assertXMLEqual(xml, expected)
        # The error is logged however.
        self.assertIn("Invalid foom details: ", self.logger.output)

    def test_merge_with_all_invalid_details(self):
        xml = self.do_merge_details(
            {
                "lshw": b"<gibber></ish>",
                "foom": b"<not>well</formed>",
                "zoom": b"<>" + factory.make_bytes(),
                "oops": None,
            }
        )
        expected = """\
            <list xmlns:foom="foom" xmlns:lshw="lshw"
                  xmlns:oops="oops" xmlns:zoom="zoom"/>
        """
        self.assertXMLEqual(xml, expected)
        # The error is logged however.
        for key in ["foom", "lshw", "zoom"]:
            self.assertIn(f"Invalid {key} details: ", self.logger.output)


class TestMergeDetails(TestMergeDetailsCleanly):
    # merge_details() differs from merge_details_cleanly() in a few
    # small ways, hence why this test case subclasses that for
    # merge_details_cleanly(), overriding tests where they produce
    # different results.

    do_merge_details = staticmethod(tags.merge_details)

    def test_merge_with_only_lshw_details(self):
        # merge_details() differs from merge_details_cleanly() in that
        # the lshw details are in the result twice: once as a
        # namespaced child of the root element, but they're also there
        # *as* the root element, without namespace.
        xml = self.do_merge_details({"lshw": b"<list><foo>Hello</foo></list>"})
        expected = """\
            <list xmlns:lshw="lshw">
              <foo>Hello</foo>
              <lshw:list>
                <lshw:foo>Hello</lshw:foo>
              </lshw:list>
            </list>
        """
        self.assertXMLEqual(xml, expected)

    def test_merge_with_multiple_details(self):
        # merge_details() differs from merge_details_cleanly() in that
        # the lshw details are in the result twice: once as a
        # namespaced child of the root element, but they're also there
        # *as* the root element, without namespace.
        xml = self.do_merge_details(
            {
                "lshw": b"<list><foo>Hello</foo></list>",
                "lldp": b"<node><foo>Hello</foo></node>",
                "zoom": b"<zoom>zoom</zoom>",
            }
        )
        expected = """\
            <list xmlns:lldp="lldp" xmlns:lshw="lshw" xmlns:zoom="zoom">
              <foo>Hello</foo>
              <lldp:node>
                <lldp:foo>Hello</lldp:foo>
              </lldp:node>
              <lshw:list>
                <lshw:foo>Hello</lshw:foo>
              </lshw:list>
              <zoom:zoom>zoom</zoom:zoom>
            </list>
        """
        self.assertXMLEqual(xml, expected)

    def test_merge_with_invalid_other_details(self):
        # merge_details() differs from merge_details_cleanly() in that
        # the lshw details are in the result twice: once as a
        # namespaced child of the root element, but they're also there
        # *as* the root element, without namespace.
        xml = self.do_merge_details(
            {
                "lshw": b"<list><foo>Hello</foo></list>",
                "foom": b"<not>well</formed>",
                "zoom": b"<zoom>zoom</zoom>",
                "oops": None,
            }
        )
        expected = """\
            <list xmlns:foom="foom" xmlns:lshw="lshw"
                  xmlns:oops="oops" xmlns:zoom="zoom">
              <foo>Hello</foo>
              <lshw:list>
                <lshw:foo>Hello</lshw:foo>
              </lshw:list>
              <zoom:zoom>zoom</zoom:zoom>
            </list>
        """
        self.assertXMLEqual(xml, expected)
        # The error is logged however.
        self.assertIn("Invalid foom details: ", self.logger.output)

    def test_merge_with_all_invalid_details(self):
        # merge_details() differs from merge_details_cleanly() in that
        # it first attempts to use the lshw details as the root #
        # element. If they're invalid the log message is therefore
        # printed first.
        xml = self.do_merge_details(
            {
                "lshw": b"<gibber></ish>",
                "foom": b"<not>well</formed>",
                "zoom": b"<>" + factory.make_bytes(),
                "oops": None,
            }
        )
        expected = """\
            <list xmlns:foom="foom" xmlns:lshw="lshw"
                  xmlns:oops="oops" xmlns:zoom="zoom"/>
        """
        self.assertXMLEqual(xml, expected)
        # The error is logged however.
        for key in ["lshw", "foom", "zoom"]:
            self.assertIn(f"Invalid {key} details: ", self.logger.output)


class TestGenBatchSlices(MAASTestCase):
    def test_batch_of_1_no_things(self):
        self.assertSequenceEqual([], list(tags.gen_batch_slices(0, 1)))

    def test_batch_of_1_one_thing(self):
        self.assertSequenceEqual(
            [slice(0, None, 1)], list(tags.gen_batch_slices(1, 1))
        )

    def test_batch_of_1_more_things(self):
        self.assertSequenceEqual(
            [slice(0, None, 3), slice(1, None, 3), slice(2, None, 3)],
            list(tags.gen_batch_slices(3, 1)),
        )

    def test_no_things(self):
        self.assertSequenceEqual([], list(tags.gen_batch_slices(0, 4)))

    def test_one_thing(self):
        self.assertSequenceEqual(
            [slice(0, None, 1)], list(tags.gen_batch_slices(1, 4))
        )

    def test_more_things(self):
        self.assertSequenceEqual(
            [slice(0, None, 3), slice(1, None, 3), slice(2, None, 3)],
            list(tags.gen_batch_slices(10, 4)),
        )

    def test_batches_by_brute_force(self):
        expected = list(range(99))
        for size in range(1, len(expected) // 2):
            slices = tags.gen_batch_slices(len(expected), size)
            batches = list(expected[sl] for sl in slices)
            # Every element in the original list is present in the
            # reconsolidated list.
            observed = sorted(chain.from_iterable(batches))
            self.assertSequenceEqual(expected, observed)
            # The longest batch is never more than 1 element longer
            # than the shortest batch.
            lens = [len(batch) for batch in batches]
            self.assertIn(max(lens) - min(lens), (0, 1))


class TestGenBatches(MAASTestCase):
    def test_batch_of_1_no_things(self):
        self.assertSequenceEqual([], list(tags.gen_batches([], 1)))

    def test_batch_of_1_one_thing(self):
        self.assertSequenceEqual([[1]], list(tags.gen_batches([1], 1)))

    def test_batch_of_1_more_things(self):
        self.assertSequenceEqual(
            [[1], [2], [3]], list(tags.gen_batches([1, 2, 3], 1))
        )

    def test_no_things(self):
        self.assertSequenceEqual([], list(tags.gen_batches([], 4)))

    def test_one_thing(self):
        self.assertSequenceEqual([[1]], list(tags.gen_batches([1], 4)))

    def test_more_things(self):
        self.assertSequenceEqual(
            [[0, 3, 6, 9], [1, 4, 7], [2, 5, 8]],
            list(tags.gen_batches(list(range(10)), 4)),
        )

    def test_brute(self):
        expected = list(range(99))
        for size in range(1, len(expected) // 2):
            batches = list(tags.gen_batches(expected, size))
            # Every element in the original list is present in the
            # reconsolidated list.
            observed = sorted(chain.from_iterable(batches))
            self.assertSequenceEqual(expected, observed)
            # The longest batch is never more than 1 element longer
            # than the shortest batch.
            lens = [len(batch) for batch in batches]
            self.assertIn(max(lens) - min(lens), (0, 1))


class TestGenNodeDetails(MAASTestCase):
    def fake_merge_details(self):
        """Modify `merge_details` to return a simple textual token.

        Specifically, it will return `merged:n1+n2+...`, where `n1`,
        `n2` and `...` are the names of the details passed into
        `merge_details`.

        This means we can test code that uses `merge_details` without
        having to come up with example XML and match on it later.
        """
        self.patch(
            tags,
            "merge_details",
            lambda mapping: "merged:" + "+".join(mapping),
        )

    def test_generates_node_details(self):
        batches = [["s1", "s2"], ["s3"]]
        responses = [
            {
                "s1": {"foo": "<node>s1</node>"},
                "s2": {"bar": "<node>s2</node>"},
            },
            {"s3": {"cob": "<node>s3</node>"}},
        ]
        get_details_for_nodes = self.patch(tags, "get_details_for_nodes")
        get_details_for_nodes.side_effect = lambda *args: responses.pop(0)
        self.fake_merge_details()
        node_details = tags.gen_node_details(sentinel.client, batches)
        self.assertCountEqual(
            [("s1", "merged:foo"), ("s2", "merged:bar"), ("s3", "merged:cob")],
            node_details,
        )
        self.assertSequenceEqual(
            [call(sentinel.client, batch) for batch in batches],
            get_details_for_nodes.mock_calls,
        )


class TestTagUpdating(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.useFixture(FakeLogger())

    def fake_client(self):
        return MAASClient(None, None, factory.make_simple_http_url())

    def test_get_details_calls_correct_api_and_parses_result(self):
        client = self.fake_client()
        data = {
            "system-1": {
                "lshw": b"<lshw><data1 /></lshw>",
                "lldp": b"<lldp><data1 /></lldp>",
            },
            "system-2": {
                "lshw": b"<lshw><data2 /></lshw>",
                "lldp": b"<lldp><data2 /></lldp>",
            },
        }
        response1 = factory.make_response(
            http.client.OK,
            bson.BSON.encode(data["system-1"]),
            "application/bson",
        )
        response2 = factory.make_response(
            http.client.OK,
            bson.BSON.encode(data["system-2"]),
            "application/bson",
        )
        get = self.patch(client, "get")
        get.side_effect = [response1, response2]
        result = tags.get_details_for_nodes(client, ["system-1", "system-2"])
        self.assertEqual(data, result)
        get.assert_has_calls(
            [
                call("/MAAS/api/2.0/nodes/system-1/", op="details"),
                call("/MAAS/api/2.0/nodes/system-2/", op="details"),
            ]
        )

    def test_post_updated_nodes_calls_correct_api_and_parses_result(self):
        client = self.fake_client()
        content = b'{"added": 1, "removed": 2}'
        response = factory.make_response(
            http.client.OK, content, "application/json"
        )
        post_mock = MagicMock(return_value=response)
        self.patch(client, "post", post_mock)
        name = factory.make_name("tag")
        rack_id = factory.make_name("rack")
        tag_definition = factory.make_name("//")
        result = tags.post_updated_nodes(
            client,
            rack_id,
            name,
            tag_definition,
            ["add-system-id"],
            ["remove-1", "remove-2"],
        )
        self.assertEqual({"added": 1, "removed": 2}, result)
        url = f"/MAAS/api/2.0/tags/{name}/"
        post_mock.assert_called_once_with(
            url,
            op="update_nodes",
            as_json=True,
            rack_controller=rack_id,
            definition=tag_definition,
            add=["add-system-id"],
            remove=["remove-1", "remove-2"],
        )

    def test_post_updated_nodes_handles_conflict(self):
        # If a worker started processing a node late, it might try to post
        # an updated list with an out-of-date definition. It gets a CONFLICT in
        # that case, which should be handled.
        client = self.fake_client()
        name = factory.make_name("tag")
        rack_id = factory.make_name("rack")
        right_tag_defintion = factory.make_name("//")
        wrong_tag_definition = factory.make_name("//")
        content = (
            "Definition supplied '%s' doesn't match"
            " current definition '%s'"
            % (wrong_tag_definition, right_tag_defintion)
        )
        err = urllib.error.HTTPError(
            "url", http.client.CONFLICT, content, {}, None
        )
        post_mock = MagicMock(side_effect=err)
        self.patch(client, "post", post_mock)
        result = tags.post_updated_nodes(
            client,
            rack_id,
            name,
            wrong_tag_definition,
            ["add-system-id"],
            ["remove-1", "remove-2"],
        )
        # self.assertEqual({'added': 1, 'removed': 2}, result)
        url = f"/MAAS/api/2.0/tags/{name}/"
        self.assertEqual({}, result)
        post_mock.assert_called_once_with(
            url,
            op="update_nodes",
            as_json=True,
            rack_controller=rack_id,
            definition=wrong_tag_definition,
            add=["add-system-id"],
            remove=["remove-1", "remove-2"],
        )

    def test_classify_evaluates_xpath(self):
        # Yay, something that doesn't need patching...
        xpath = etree.XPath("//node")
        xml = etree.fromstring
        node_details = [
            ("a", xml("<node />")),
            ("b", xml("<not-node />")),
            ("c", xml("<parent><node /></parent>")),
        ]
        self.assertEqual(
            (["a", "c"], ["b"]), tags.classify(xpath, node_details)
        )

    def test_process_node_tags_integration(self):
        self.useFixture(
            ClusterConfigurationFixture(
                maas_url=factory.make_simple_http_url()
            )
        )
        get_hw_system1 = factory.make_response(
            http.client.OK,
            bson.BSON.encode({"lshw": b"<node />"}),
            "application/bson",
        )
        get_hw_system2 = factory.make_response(
            http.client.OK,
            bson.BSON.encode({"lshw": b"<not-node />"}),
            "application/bson",
        )
        mock_get = self.patch(MAASClient, "get")
        mock_get.side_effect = [get_hw_system1, get_hw_system2]
        mock_post = self.patch(MAASClient, "post")
        mock_post.return_value = factory.make_response(
            http.client.OK, b'{"added": 1, "removed": 1}', "application/json"
        )
        tag_name = factory.make_name("tag")
        tag_definition = "//lshw:node"
        tag_nsmap = {"lshw": "lshw"}
        rack_id = factory.make_name("rack")
        tags.process_node_tags(
            rack_id,
            [{"system_id": "system-id1"}, {"system_id": "system-id2"}],
            tag_name,
            tag_definition,
            tag_nsmap,
            self.fake_client(),
        )
        tag_url = f"/MAAS/api/2.0/tags/{tag_name}/"
        mock_post.assert_called_once_with(
            tag_url,
            as_json=True,
            op="update_nodes",
            rack_controller=rack_id,
            definition=tag_definition,
            add=["system-id1"],
            remove=["system-id2"],
        )
