# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for tag updating."""

from functools import partial
from itertools import chain
from textwrap import dedent

from fixtures import FakeLogger
from lxml import etree

from apiclient.maas_client import MAASClient
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver import tags
from provisioningserver.utils import classify


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


class TestTagUpdating(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.useFixture(FakeLogger())

    def fake_client(self):
        return MAASClient(None, None, factory.make_simple_http_url())

    def test_classify_evaluates_xpath(self):
        # Yay, something that doesn't need patching...
        xpath = etree.XPath("//node")
        xml = etree.fromstring
        node_details = [
            ("a", xml("<node />")),
            ("b", xml("<not-node />")),
            ("c", xml("<parent><node /></parent>")),
        ]
        self.assertEqual((["a", "c"], ["b"]), classify(xpath, node_details))
