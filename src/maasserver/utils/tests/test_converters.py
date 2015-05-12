# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for converters utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from textwrap import dedent

from maasserver.utils.converters import (
    human_readable_bytes,
    XMLToYAML,
)
from maastesting.testcase import MAASTestCase


class TestXMLToYAML(MAASTestCase):

    def test_xml_to_yaml_converts_xml(self):
        # This test is similar to the test above but this one
        # checks that tags with colons works as expected.
        xml = """
        <list xmlns:lldp="lldp" xmlns:lshw="lshw">
         <lldp:lldp label="LLDP neighbors"/>
         <lshw:list>Some Content</lshw:list>
        </list>
        """
        expected_result = dedent("""\
        - list:
          - lldp:lldp:
            label: LLDP neighbors
          - lshw:list:
            Some Content
        """)
        yml = XMLToYAML(xml)
        self.assertEqual(
            yml.convert(), expected_result)


class TestHumanReadableBytes(MAASTestCase):

    scenarios = [
        ("bytes", dict(
            size=987,
            output="987.0", suffix="bytes")),
        ("KB", dict(
            size=1000 * 35 + 500,
            output="35.5", suffix="KB")),
        ("MB", dict(
            size=(1000 ** 2) * 28,
            output="28.0", suffix="MB")),
        ("GB", dict(
            size=(1000 ** 3) * 72,
            output="72.0", suffix="GB")),
        ("TB", dict(
            size=(1000 ** 4) * 150,
            output="150.0", suffix="TB")),
        ("PB", dict(
            size=(1000 ** 5),
            output="1.0", suffix="PB")),
        ("EB", dict(
            size=(1000 ** 6),
            output="1.0", suffix="EB")),
        ("ZB", dict(
            size=(1000 ** 7),
            output="1.0", suffix="ZB")),
        ("YB", dict(
            size=(1000 ** 8),
            output="1.0", suffix="YB")),
        ]

    def test__returns_size_with_suffix(self):
        self.assertEqual(
            '%s %s' % (self.output, self.suffix),
            human_readable_bytes(self.size))

    def test__returns_size_without_suffix(self):
        self.assertEqual(
            self.output,
            human_readable_bytes(self.size, include_suffix=False))
