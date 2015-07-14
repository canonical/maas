# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Conversion utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'XMLToYAML',
    ]

from lxml import etree


class XMLToYAML:
    """Convert XML to YAML."""

    def __init__(self, text):
        self.text = text
        self.new_text = ''
        self.level = 0
        self.indent_spaces = 2

    def spaces(self):
        return self.level * self.indent_spaces * ' '

    def addText(self, element):
        if '{' in element.tag:
            new_tag = element.tag.strip('{').replace('}', ':')
            self.new_text += "%s- %s:\n" % (self.spaces(), new_tag)
        else:
            self.new_text += "%s- %s:\n" % (self.spaces(), element.tag)
        self.level += 1
        for key in element.keys():
            self.new_text += "%s%s: %s\n" % (
                self.spaces(), key, element.attrib[key])

    def recurseElement(self, element):
        for child in element.iterchildren():
            self.addText(child)
            if child.text is not None and not child.text.isspace():
                self.new_text += "%s%s\n" % (self.spaces(), child.text.strip())
            self.recurseElement(child)
            self.level -= 1

    def convert(self):
        root = etree.fromstring(self.text)
        self.addText(root)
        self.recurseElement(root)
        return self.new_text


def human_readable_bytes(num_bytes, include_suffix=True):
    """Return the human readable text for bytes. (SI units)

    :param num_bytes: Bytes to be converted. Can't be None
    :param include_suffix: Whether to include the computed suffix in the
        output.
    """
    for unit in ['bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']:
        if abs(num_bytes) < 1000.0 or unit == 'YB':
            if include_suffix:
                return "%3.1f %s" % (num_bytes, unit)
            else:
                return "%3.1f" % num_bytes
        num_bytes /= 1000.0


def machine_readable_bytes(humanized):
    """Return the integer for a number of bytes in text form. (SI units)

    Accepts 'K', 'M', 'G', 'T', 'P' and 'E'

    NOT AN EXACT COUNTERPART TO human_readable_bytes!

    :param humanized: string be converted.
    """
    if humanized == '' or humanized is None:
        return None
    elif humanized.endswith('K') or humanized.endswith('k'):
        return int(humanized[:-1]) * 1000
    elif humanized.endswith('M') or humanized.endswith('m'):
        return int(humanized[:-1]) * 1000000
    elif humanized.endswith('G') or humanized.endswith('g'):
        return int(humanized[:-1]) * 1000000000
    elif humanized.endswith('T') or humanized.endswith('t'):
        return int(humanized[:-1]) * 1000000000000
    elif humanized.endswith('P') or humanized.endswith('p'):
        return int(humanized[:-1]) * 1000000000000000
    elif humanized.endswith('E') or humanized.endswith('e'):
        return int(humanized[:-1]) * 1000000000000000000
    else:
        return int(humanized)
