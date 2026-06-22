# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from itertools import chain
import re

# supported input MAC formats
MAC_FIELD_RE = re.compile(
    r"^"
    r"([0-9a-fA-F]{1,2}:){5}[0-9a-fA-F]{1,2}|"  # aa:bb:cc:dd:ee:ff
    r"([0-9a-fA-F]{1,2}-){5}[0-9a-fA-F]{1,2}|"  # aa-bb-cc-dd-ee-ff
    r"([0-9a-fA-F]{3,4}.){2}[0-9a-fA-F]{3,4}"  # aabb.ccdd.eeff
    r"$"
)
# MAC format for DB storage
MAC_RE = re.compile(r"^([0-9a-fA-F]{1,2}:){5}[0-9a-fA-F]{1,2}$")

MAC_SPLIT_RE = re.compile(r"[-:.]")


def normalise_macaddress(mac: str) -> str:
    """Return a colon-separated format for the specified MAC.

    This supports converting from input formats matching the MAC_FIELD_RE
    regexp.

    """

    tokens = MAC_SPLIT_RE.split(mac.lower())
    match len(tokens):
        case 1:  # no separator
            tokens = re.findall("..", tokens[0])
        case 3:  # each token is two bytes
            tokens = chain(
                *(re.findall("..", token.zfill(4)) for token in tokens)
            )
        case _:  # single-byte tokens
            tokens = (token.zfill(2) for token in tokens)
    return ":".join(tokens)


def normalise_mac_query(value: str) -> str:
    """Return a separator-less, lowercase form of a full or partial MAC.

    Unlike ``normalise_macaddress``, this accepts partial fragments and does
    not pad or group, so it can be used to build format-agnostic
    ``startswith``/``contains`` queries against the separator-less form of the
    stored MAC address.
    """
    return MAC_SPLIT_RE.sub("", value.lower())
