# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for tag updating."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import doctest
import httplib
import io
from itertools import chain
import json
from textwrap import dedent
import urllib2

from apiclient.maas_client import MAASClient
import bson
from fixtures import FakeLogger
from lxml import etree
from maastesting.factory import factory
from maastesting.fakemethod import (
    FakeMethod,
    MultiFakeMethod,
    )
from maastesting.matchers import IsCallable
from mock import (
    call,
    MagicMock,
    sentinel,
    )
from provisioningserver import tags
from provisioningserver.auth import get_recorded_nodegroup_uuid
from provisioningserver.testing.testcase import PservTestCase
from testtools.matchers import (
    DocTestMatches,
    Equals,
    MatchesStructure,
    )


def make_response(status_code, content, content_type=None):
    """Return a similar response to that which `urllib2` returns."""
    if content_type is None:
        headers_raw = b""
    else:
        if isinstance(content_type, unicode):
            content_type = content_type.encode("ascii")
        headers_raw = b"Content-Type: %s" % content_type
    headers = httplib.HTTPMessage(io.BytesIO(headers_raw))
    return urllib2.addinfourl(
        fp=io.BytesIO(content), headers=headers,
        url=None, code=status_code)


class TestProcessResponse(PservTestCase):

    def setUp(self):
        super(TestProcessResponse, self).setUp()
        self.useFixture(FakeLogger())

    def test_process_OK_response_with_JSON_content(self):
        data = {"abc": 123}
        response = make_response(
            httplib.OK, json.dumps(data), "application/json")
        self.assertEqual(data, tags.process_response(response))

    def test_process_OK_response_with_BSON_content(self):
        data = {"abc": 123}
        response = make_response(
            httplib.OK, bson.BSON.encode(data), "application/bson")
        self.assertEqual(data, tags.process_response(response))

    def test_process_OK_response_with_other_content(self):
        data = factory.getRandomBytes()
        response = make_response(
            httplib.OK, data, "application/octet-stream")
        self.assertEqual(data, tags.process_response(response))

    def test_process_not_OK_response(self):
        response = make_response(httplib.NOT_FOUND, b"", "application/json")
        response.url = factory.getRandomString()
        error = self.assertRaises(
            urllib2.HTTPError, tags.process_response, response)
        self.assertThat(
            error, MatchesStructure.byEquality(
                url=response.url, code=response.code,
                msg="Not Found, expected 200 OK",
                headers=response.headers, fp=response.fp))


class EqualsXML(Equals):

    @staticmethod
    def normalise(xml):
        if isinstance(xml, (bytes, unicode)):
            xml = etree.fromstring(dedent(xml))
        return etree.tostring(xml, pretty_print=True)

    def __init__(self, tree):
        super(EqualsXML, self).__init__(self.normalise(tree))

    def match(self, other):
        return super(EqualsXML, self).match(self.normalise(other))


class TestMergeDetailsCleanly(PservTestCase):

    do_merge_details = staticmethod(tags.merge_details_cleanly)

    def setUp(self):
        super(TestMergeDetailsCleanly, self).setUp()
        self.logger = self.useFixture(FakeLogger())

    def test_merge_with_no_details(self):
        xml = self.do_merge_details({})
        self.assertThat(xml, EqualsXML("<list/>"))

    def test_merge_with_only_lshw_details(self):
        xml = self.do_merge_details(
            {"lshw": b"<list><foo>Hello</foo></list>"})
        expected = """\
            <list xmlns:lshw="lshw">
              <lshw:list>
                <lshw:foo>Hello</lshw:foo>
              </lshw:list>
            </list>
        """
        self.assertThat(xml, EqualsXML(expected))

    def test_merge_with_only_lldp_details(self):
        xml = self.do_merge_details(
            {"lldp": b"<node><foo>Hello</foo></node>"})
        expected = """\
            <list xmlns:lldp="lldp">
              <lldp:node>
                <lldp:foo>Hello</lldp:foo>
              </lldp:node>
            </list>
        """
        self.assertThat(xml, EqualsXML(expected))

    def test_merge_with_multiple_details(self):
        xml = self.do_merge_details({
            "lshw": b"<list><foo>Hello</foo></list>",
            "lldp": b"<node><foo>Hello</foo></node>",
            "zoom": b"<zoom>zoom</zoom>",
        })
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
        self.assertThat(xml, EqualsXML(expected))

    def test_merges_into_new_tree(self):
        xml = self.do_merge_details({
            "lshw": b"<list><foo>Hello</foo></list>",
            "lldp": b"<node><foo>Hello</foo></node>",
        })
        # The presence of a getroot() method indicates that this is a
        # tree object, not an element.
        self.assertThat(xml, MatchesStructure(getroot=IsCallable()))
        # The list tag can be obtained using an XPath expression
        # starting from the root of the tree.
        self.assertSequenceEqual(
            ["list"], [elem.tag for elem in xml.xpath("/list")])

    def assertDocTestMatches(self, expected, observed):
        return self.assertThat(observed, DocTestMatches(
            dedent(expected), doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE))

    def test_merge_with_invalid_lshw_details(self):
        # The lshw details cannot be parsed, but merge_details_cleanly() still
        # returns a usable tree, albeit without any lshw details.
        xml = self.do_merge_details({"lshw": b"<not>well</formed>"})
        self.assertThat(xml, EqualsXML('<list xmlns:lshw="lshw"/>'))
        # The error is logged however.
        self.assertDocTestMatches(
            """\
            Invalid lshw details: ...
            """,
            self.logger.output)

    def test_merge_with_invalid_lshw_details_and_others_valid(self):
        # The lshw details cannot be parsed, but merge_details_cleanly() still
        # returns a usable tree, albeit without any lshw details.
        xml = self.do_merge_details({
            "lshw": b"<not>well</formed>",
            "lldp": b"<node><foo>Hello</foo></node>",
            "zoom": b"<zoom>zoom</zoom>",
        })
        expected = """\
            <list xmlns:lldp="lldp" xmlns:lshw="lshw" xmlns:zoom="zoom">
              <lldp:node>
                <lldp:foo>Hello</lldp:foo>
              </lldp:node>
              <zoom:zoom>zoom</zoom:zoom>
            </list>
        """
        self.assertThat(xml, EqualsXML(expected))
        # The error is logged however.
        self.assertDocTestMatches(
            """\
            Invalid lshw details: ...
            """,
            self.logger.output)

    def test_merge_with_invalid_other_details(self):
        xml = self.do_merge_details({
            "lshw": b"<list><foo>Hello</foo></list>",
            "foom": b"<not>well</formed>",
            "zoom": b"<zoom>zoom</zoom>",
            "oops": None,
        })
        expected = """\
            <list xmlns:foom="foom" xmlns:lshw="lshw"
                  xmlns:oops="oops" xmlns:zoom="zoom">
              <lshw:list>
                <lshw:foo>Hello</lshw:foo>
              </lshw:list>
              <zoom:zoom>zoom</zoom:zoom>
            </list>
        """
        self.assertThat(xml, EqualsXML(expected))
        # The error is logged however.
        self.assertDocTestMatches(
            """\
            Invalid foom details: ...
            """,
            self.logger.output)

    def test_merge_with_all_invalid_details(self):
        xml = self.do_merge_details({
            "lshw": b"<gibber></ish>",
            "foom": b"<not>well</formed>",
            "zoom": b"<>" + factory.getRandomBytes(),
            "oops": None,
        })
        expected = """\
            <list xmlns:foom="foom" xmlns:lshw="lshw"
                  xmlns:oops="oops" xmlns:zoom="zoom"/>
        """
        self.assertThat(xml, EqualsXML(expected))
        # The error is logged however.
        self.assertDocTestMatches(
            """\
            Invalid foom details: ...
            Invalid lshw details: ...
            Invalid zoom details: ...
            """,
            self.logger.output)


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
        self.assertThat(xml, EqualsXML(expected))

    def test_merge_with_multiple_details(self):
        # merge_details() differs from merge_details_cleanly() in that
        # the lshw details are in the result twice: once as a
        # namespaced child of the root element, but they're also there
        # *as* the root element, without namespace.
        xml = self.do_merge_details({
            "lshw": b"<list><foo>Hello</foo></list>",
            "lldp": b"<node><foo>Hello</foo></node>",
            "zoom": b"<zoom>zoom</zoom>",
        })
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
        self.assertThat(xml, EqualsXML(expected))

    def test_merge_with_invalid_other_details(self):
        # merge_details() differs from merge_details_cleanly() in that
        # the lshw details are in the result twice: once as a
        # namespaced child of the root element, but they're also there
        # *as* the root element, without namespace.
        xml = self.do_merge_details({
            "lshw": b"<list><foo>Hello</foo></list>",
            "foom": b"<not>well</formed>",
            "zoom": b"<zoom>zoom</zoom>",
            "oops": None,
        })
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
        self.assertThat(xml, EqualsXML(expected))
        # The error is logged however.
        self.assertDocTestMatches(
            """\
            Invalid foom details: ...
            """,
            self.logger.output)

    def test_merge_with_all_invalid_details(self):
        # merge_details() differs from merge_details_cleanly() in that
        # it first attempts to use the lshw details as the root #
        # element. If they're invalid the log message is therefore
        # printed first.
        xml = self.do_merge_details({
            "lshw": b"<gibber></ish>",
            "foom": b"<not>well</formed>",
            "zoom": b"<>" + factory.getRandomBytes(),
            "oops": None,
        })
        expected = """\
            <list xmlns:foom="foom" xmlns:lshw="lshw"
                  xmlns:oops="oops" xmlns:zoom="zoom"/>
        """
        self.assertThat(xml, EqualsXML(expected))
        # The error is logged however.
        self.assertDocTestMatches(
            """\
            Invalid lshw details: ...
            Invalid foom details: ...
            Invalid zoom details: ...
            """,
            self.logger.output)


class TestGenBatchSlices(PservTestCase):

    def test_batch_of_1_no_things(self):
        self.assertSequenceEqual(
            [], list(tags.gen_batch_slices(0, 1)))

    def test_batch_of_1_one_thing(self):
        self.assertSequenceEqual(
            [slice(0, None, 1)], list(tags.gen_batch_slices(1, 1)))

    def test_batch_of_1_more_things(self):
        self.assertSequenceEqual(
            [slice(0, None, 3), slice(1, None, 3), slice(2, None, 3)],
            list(tags.gen_batch_slices(3, 1)))

    def test_no_things(self):
        self.assertSequenceEqual(
            [], list(tags.gen_batch_slices(0, 4)))

    def test_one_thing(self):
        self.assertSequenceEqual(
            [slice(0, None, 1)], list(tags.gen_batch_slices(1, 4)))

    def test_more_things(self):
        self.assertSequenceEqual(
            [slice(0, None, 3), slice(1, None, 3), slice(2, None, 3)],
            list(tags.gen_batch_slices(10, 4)))

    def test_batches_by_brute_force(self):
        expected = range(99)
        for size in xrange(1, len(expected) // 2):
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


class TestGenBatches(PservTestCase):

    def test_batch_of_1_no_things(self):
        self.assertSequenceEqual(
            [], list(tags.gen_batches([], 1)))

    def test_batch_of_1_one_thing(self):
        self.assertSequenceEqual(
            [[1]], list(tags.gen_batches([1], 1)))

    def test_batch_of_1_more_things(self):
        self.assertSequenceEqual(
            [[1], [2], [3]], list(tags.gen_batches([1, 2, 3], 1)))

    def test_no_things(self):
        self.assertSequenceEqual(
            [], list(tags.gen_batches([], 4)))

    def test_one_thing(self):
        self.assertSequenceEqual(
            [[1]], list(tags.gen_batches([1], 4)))

    def test_more_things(self):
        self.assertSequenceEqual(
            [[0, 3, 6, 9], [1, 4, 7], [2, 5, 8]],
            list(tags.gen_batches(range(10), 4)))

    def test_brute(self):
        expected = range(99)
        for size in xrange(1, len(expected) // 2):
            batches = list(tags.gen_batches(expected, size))
            # Every element in the original list is present in the
            # reconsolidated list.
            observed = sorted(chain.from_iterable(batches))
            self.assertSequenceEqual(expected, observed)
            # The longest batch is never more than 1 element longer
            # than the shortest batch.
            lens = [len(batch) for batch in batches]
            self.assertIn(max(lens) - min(lens), (0, 1))


class TestGenNodeDetails(PservTestCase):

    def fake_merge_details(self):
        """Modify `merge_details` to return a simple textual token.

        Specifically, it will return `merged:n1+n2+...`, where `n1`,
        `n2` and `...` are the names of the details passed into
        `merge_details`.

        This means we can test code that uses `merge_details` without
        having to come up with example XML and match on it later.
        """
        self.patch(
            tags, "merge_details",
            lambda mapping: "merged:" + "+".join(mapping))

    def test(self):
        batches = [["s1", "s2"], ["s3"]]
        responses = [
            {"s1": {"foo": "<node>s1</node>"},
             "s2": {"bar": "<node>s2</node>"}},
            {"s3": {"cob": "<node>s3</node>"}},
        ]
        get_details_for_nodes = self.patch(tags, "get_details_for_nodes")
        get_details_for_nodes.side_effect = lambda *args: responses.pop(0)
        self.fake_merge_details()
        node_details = tags.gen_node_details(
            sentinel.client, sentinel.uuid, batches)
        self.assertItemsEqual(
            [('s1', 'merged:foo'), ('s2', 'merged:bar'), ('s3', 'merged:cob')],
            node_details)
        self.assertSequenceEqual(
            [call(sentinel.client, sentinel.uuid, batch) for batch in batches],
            get_details_for_nodes.mock_calls)


class TestTagUpdating(PservTestCase):

    def setUp(self):
        super(TestTagUpdating, self).setUp()
        self.useFixture(FakeLogger())

    def test_get_cached_knowledge_knows_nothing(self):
        # If we haven't given it any secrets, we should get back nothing
        self.assertEqual((None, None), tags.get_cached_knowledge())

    def test_get_cached_knowledge_with_only_url(self):
        self.set_maas_url()
        self.assertEqual((None, None), tags.get_cached_knowledge())

    def test_get_cached_knowledge_with_only_url_creds(self):
        self.set_maas_url()
        self.set_api_credentials()
        self.assertEqual((None, None), tags.get_cached_knowledge())

    def test_get_cached_knowledge_with_all_info(self):
        self.set_maas_url()
        self.set_api_credentials()
        self.set_node_group_uuid()
        client, uuid = tags.get_cached_knowledge()
        self.assertIsNot(None, client)
        self.assertIsInstance(client, MAASClient)
        self.assertIsNot(None, uuid)
        self.assertEqual(get_recorded_nodegroup_uuid(), uuid)

    def fake_client(self):
        return MAASClient(None, None, self.make_maas_url())

    def fake_cached_knowledge(self):
        nodegroup_uuid = factory.make_name('nodegroupuuid')
        return self.fake_client(), nodegroup_uuid

    def test_get_nodes_calls_correct_api_and_parses_result(self):
        client, uuid = self.fake_cached_knowledge()
        response = make_response(
            httplib.OK,
            b'["system-id1", "system-id2"]',
            'application/json',
        )
        mock = MagicMock(return_value=response)
        self.patch(client, 'get', mock)
        result = tags.get_nodes_for_node_group(client, uuid)
        self.assertEqual(['system-id1', 'system-id2'], result)
        url = '/api/1.0/nodegroups/%s/' % (uuid,)
        mock.assert_called_once_with(url, op='list_nodes')

    def test_get_details_calls_correct_api_and_parses_result(self):
        client, uuid = self.fake_cached_knowledge()
        data = {
            "system-1": {
                "lshw": bson.binary.Binary(b"<lshw><data1 /></lshw>"),
                "lldp": bson.binary.Binary(b"<lldp><data1 /></lldp>"),
            },
            "system-2": {
                "lshw": bson.binary.Binary(b"<lshw><data2 /></lshw>"),
                "lldp": bson.binary.Binary(b"<lldp><data2 /></lldp>"),
            },
        }
        content = bson.BSON.encode(data)
        response = make_response(httplib.OK, content, 'application/bson')
        post = self.patch(client, 'post')
        post.return_value = response
        result = tags.get_details_for_nodes(
            client, uuid, ['system-1', 'system-2'])
        self.assertEqual(data, result)
        url = '/api/1.0/nodegroups/%s/' % (uuid,)
        post.assert_called_once_with(
            url, op='details', system_ids=["system-1", "system-2"])

    def test_post_updated_nodes_calls_correct_api_and_parses_result(self):
        client, uuid = self.fake_cached_knowledge()
        content = b'{"added": 1, "removed": 2}'
        response = make_response(httplib.OK, content, 'application/json')
        post_mock = MagicMock(return_value=response)
        self.patch(client, 'post', post_mock)
        name = factory.make_name('tag')
        tag_definition = factory.make_name('//')
        result = tags.post_updated_nodes(
            client, name, tag_definition, uuid,
            ['add-system-id'], ['remove-1', 'remove-2'])
        self.assertEqual({'added': 1, 'removed': 2}, result)
        url = '/api/1.0/tags/%s/' % (name,)
        post_mock.assert_called_once_with(
            url, op='update_nodes', as_json=True, nodegroup=uuid,
            definition=tag_definition,
            add=['add-system-id'], remove=['remove-1', 'remove-2'])

    def test_post_updated_nodes_handles_conflict(self):
        # If a worker started processing a node late, it might try to post
        # an updated list with an out-of-date definition. It gets a CONFLICT in
        # that case, which should be handled.
        client, uuid = self.fake_cached_knowledge()
        name = factory.make_name('tag')
        right_tag_defintion = factory.make_name('//')
        wrong_tag_definition = factory.make_name('//')
        content = ("Definition supplied '%s' doesn't match"
                   " current definition '%s'"
                   % (wrong_tag_definition, right_tag_defintion))
        err = urllib2.HTTPError('url', httplib.CONFLICT, content, {}, None)
        post_mock = MagicMock(side_effect=err)
        self.patch(client, 'post', post_mock)
        result = tags.post_updated_nodes(
            client, name, wrong_tag_definition,
            uuid, ['add-system-id'], ['remove-1', 'remove-2'])
        # self.assertEqual({'added': 1, 'removed': 2}, result)
        url = '/api/1.0/tags/%s/' % (name,)
        self.assertEqual({}, result)
        post_mock.assert_called_once_with(
            url, op='update_nodes', as_json=True, nodegroup=uuid,
            definition=wrong_tag_definition,
            add=['add-system-id'], remove=['remove-1', 'remove-2'])

    def test_classify_evaluates_xpath(self):
        # Yay, something that doesn't need patching...
        xpath = etree.XPath('//node')
        xml = etree.fromstring
        node_details = [
            ('a', xml('<node />')),
            ('b', xml('<not-node />')),
            ('c', xml('<parent><node /></parent>')),
        ]
        self.assertEqual(
            (['a', 'c'], ['b']),
            tags.classify(xpath, node_details))

    def test_process_node_tags_no_secrets(self):
        self.patch(MAASClient, 'get')
        self.patch(MAASClient, 'post')
        tag_name = factory.make_name('tag')
        self.assertRaises(
            tags.MissingCredentials,
            tags.process_node_tags, tag_name, '//node', None)
        self.assertFalse(MAASClient.get.called)
        self.assertFalse(MAASClient.post.called)

    def test_process_node_tags_integration(self):
        self.set_secrets()
        get_nodes = FakeMethod(
            result=make_response(
                httplib.OK,
                b'["system-id1", "system-id2"]',
                'application/json',
            ))
        post_hw_details = FakeMethod(
            result=make_response(
                httplib.OK,
                bson.BSON.encode({
                    'system-id1': {'lshw': b'<node />'},
                    'system-id2': {'lshw': b'<not-node />'},
                }),
                'application/bson',
            ))
        get_fake = MultiFakeMethod([get_nodes])
        post_update_fake = FakeMethod(
            result=make_response(
                httplib.OK,
                b'{"added": 1, "removed": 1}',
                'application/json',
            ))
        post_fake = MultiFakeMethod([post_hw_details, post_update_fake])
        self.patch(MAASClient, 'get', get_fake)
        self.patch(MAASClient, 'post', post_fake)
        tag_name = factory.make_name('tag')
        nodegroup_uuid = get_recorded_nodegroup_uuid()
        tag_definition = '//lshw:node'
        tag_nsmap = {"lshw": "lshw"}
        tags.process_node_tags(tag_name, tag_definition, tag_nsmap=tag_nsmap)
        nodegroup_url = '/api/1.0/nodegroups/%s/' % (nodegroup_uuid,)
        tag_url = '/api/1.0/tags/%s/' % (tag_name,)
        self.assertEqual(
            [((nodegroup_url,), {'op': 'list_nodes'})],
            get_nodes.calls)
        self.assertEqual(
            [
                ((nodegroup_url,), {
                    'op': 'details',
                    'system_ids': ['system-id1', 'system-id2'],
                }),
            ],
            post_hw_details.calls)
        self.assertEqual(
            [
                ((tag_url,), {
                    'as_json': True,
                    'op': 'update_nodes',
                    'nodegroup': nodegroup_uuid,
                    'definition': tag_definition,
                    'add': ['system-id1'],
                    'remove': ['system-id2'],
                }),
            ],
            post_update_fake.calls)

    def test_process_node_tags_requests_details_in_batches(self):
        client = object()
        uuid = factory.make_name('nodegroupuuid')
        self.patch(
            tags, 'get_cached_knowledge',
            MagicMock(return_value=(client, uuid)))
        self.patch(
            tags, 'get_nodes_for_node_group',
            MagicMock(return_value=['a', 'b', 'c']))
        fake_first = FakeMethod(result={
            'a': {'lshw': b'<node />'},
            'c': {'lshw': b'<parent><node /></parent>'},
        })
        fake_second = FakeMethod(result={
            'b': {'lshw': b'<not-node />'},
        })
        self.patch(
            tags, 'get_details_for_nodes',
            MultiFakeMethod([fake_first, fake_second]))
        self.patch(tags, 'post_updated_nodes')
        tag_name = factory.make_name('tag')
        tag_definition = '//node'
        tags.process_node_tags(
            tag_name, tag_definition, tag_nsmap=None, batch_size=2)
        tags.get_cached_knowledge.assert_called_once_with()
        tags.get_nodes_for_node_group.assert_called_once_with(client, uuid)
        self.assertEqual([((client, uuid, ['a', 'c']), {})], fake_first.calls)
        self.assertEqual([((client, uuid, ['b']), {})], fake_second.calls)
        tags.post_updated_nodes.assert_called_once_with(
            client, tag_name, tag_definition, uuid, ['a', 'c'], ['b'])
