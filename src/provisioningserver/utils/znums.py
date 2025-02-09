# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Convert integers to the arbitrarily-named 'z numbers', and back.

A z number is a representation of a number using 24 unambiguous alphanumeric
digits. Put another way, it's a base-24 number with a custom alphabet.
"""

from itertools import count

zchars = "34678abcdefghkmnpqrstwxy"
znums = dict(zip(zchars, count(0)))


def from_int(num, _chars=zchars):
    parts, div = [], len(_chars)
    while num > 0:
        num, rem = divmod(num, div)
        parts.append(_chars[rem])
    if len(parts) == 0:
        return _chars[0]
    else:
        return "".join(parts[::-1])


def to_int(zs, _nums=znums):
    total, div = 0, len(_nums)
    for char, exp in zip(zs[::-1], count(0)):
        total += _nums[char] * (div**exp)
    return total
