# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Conversion utilities."""


from datetime import timedelta
import json
import re

from django.conf import settings
from lxml import etree


class XMLToYAML:
    """Convert XML to YAML."""

    def __init__(self, text):
        self.text = text
        self.new_text = ""
        self.level = 0
        self.indent_spaces = 2

    def spaces(self):
        return self.level * self.indent_spaces * " "

    def addText(self, element):
        if "{" in element.tag:
            new_tag = element.tag.strip("{").replace("}", ":")
            self.new_text += f"{self.spaces()}- {new_tag}:\n"
        else:
            self.new_text += f"{self.spaces()}- {element.tag}:\n"
        self.level += 1
        for key in element.keys():
            self.new_text += "{}{}: {}\n".format(
                self.spaces(),
                key,
                element.attrib[key],
            )

    def recurseElement(self, element):
        for child in element.iterchildren():
            self.addText(child)
            if child.text is not None and not child.text.isspace():
                self.new_text += f"{self.spaces()}{child.text.strip()}\n"
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
    # Case is important: 1kB is 1000 bytes, whereas 1KB is 1024 bytes. See
    # https://en.wikipedia.org/wiki/Byte#Unit_symbol
    for unit in ["bytes", "kB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]:
        if abs(num_bytes) < 1000.0 or unit == "YB":
            if include_suffix:
                if unit == "bytes":
                    return f"{num_bytes:.0f} {unit}"
                else:
                    return f"{num_bytes:.1f} {unit}"
            else:
                if unit == "bytes":
                    return "%.0f" % num_bytes
                else:
                    return "%.1f" % num_bytes
        num_bytes /= 1000.0


def machine_readable_bytes(humanized):
    """Return the integer for a number of bytes in text form. (SI units)

    Accepts 'K', 'M', 'G', 'T', 'P' and 'E'

    NOT AN EXACT COUNTERPART TO human_readable_bytes!

    :param humanized: string be converted.
    """
    if humanized == "" or humanized is None:
        return None
    elif humanized.endswith("K") or humanized.endswith("k"):
        return int(humanized[:-1]) * 1000
    elif humanized.endswith("M") or humanized.endswith("m"):
        return int(humanized[:-1]) * 1000000
    elif humanized.endswith("G") or humanized.endswith("g"):
        return int(humanized[:-1]) * 1000000000
    elif humanized.endswith("T") or humanized.endswith("t"):
        return int(humanized[:-1]) * 1000000000000
    elif humanized.endswith("P") or humanized.endswith("p"):
        return int(humanized[:-1]) * 1000000000000000
    elif humanized.endswith("E") or humanized.endswith("e"):
        return int(humanized[:-1]) * 1000000000000000000
    else:
        return int(humanized)


def round_size_to_nearest_block(size, block_size, round_up=True):
    """Round the size to the nearest block returning the new size.

    :param size: The requested size to round.
    :param block_size: The block size to round to.
    :param round_up: If True, will round up to fill current block, else down.
    """
    number_of_blocks = size // block_size
    if round_up and size % block_size > 0:
        number_of_blocks += 1
    return block_size * number_of_blocks


def json_load_bytes(input: bytes, encoding=None) -> dict:
    """Load JSON from `input`.

    :param input: Input data to convert from JSON.
    :type input: bytes
    :param encoding: Encoding to use to decode input. Defaults to Django's
        ``DEFAULT_CHARSET``.
    :type encoding: str
    """
    return json.loads(
        input.decode(
            settings.DEFAULT_CHARSET if encoding is None else encoding
        )
    )


_duration_re = re.compile(
    r"((?P<hours>\d+?)(\s?(hour(s?)|hr|h))\s?)?((?P<minutes>\d+?)(\s?(minute(s?)|min|m))\s?)?((?P<seconds>\d+?)(\s?(second(s?)|sec|s))\s?)?"
)


def parse_systemd_interval(interval):
    duration = _duration_re.match(interval)
    if not duration.group():
        raise ValueError("value is not a valid interval")
    duration = duration.groupdict()
    params = {name: int(t) for name, t in duration.items() if t}
    return timedelta(**params).total_seconds()


def systemd_interval_to_calendar(interval):
    duration = _duration_re.match(interval)
    if not duration.group():
        raise ValueError("value is not a valid interval")
    duration = duration.groupdict()
    hours = duration.get("hours")
    minutes = duration.get("minutes")
    seconds = duration.get("seconds")
    hour_interval = f"00/{hours}" if hours and hours != "1" else "*"
    second_interval = f"00/{seconds}" if seconds else "00"
    minute_interval = (
        f"00/{minutes}"
        if minutes
        else "00" if second_interval == "00" else "*"
    )

    return f"*-*-* {hour_interval}:{minute_interval}:{second_interval}"
