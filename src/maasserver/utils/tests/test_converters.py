# Copyright 2014 Canonical Ltd.  This software is licensed under the
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

from maasserver.utils.converters import XMLToYAML
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
