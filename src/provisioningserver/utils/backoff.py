# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities related to back-off.

Many or most of the following are inspired by `Exponential Backoff And
Jitter`__ on the AWS Architecture Blog.

.. __: http://www.awsarchitectureblog.com/2015/03/backoff.html.

"""

from itertools import count
from random import random


def exponential_growth(base, rate):
    """Generate successive values for an exponential growth curve.

    Intervals are discrete and fixed, starting at 1 (not 0) and increasing by
    1 on each iteration.

    :param base: The starting value, i.e. where the interval is 0.0.
    :type base: float
    :param rate: The rate of growth. For a 5% growth rate, pass 1.05.
    :type rate: float.
    """
    for attempt in count(1):
        yield base * (rate**attempt)


def full_jitter(values):
    """Apply "full jitter" to `values`.

    Each value in `values` will be multiplied by a random number in the
    interval [0.0, 1.0).

    :param values: An iterable of numbers.
    """
    for value in values:
        yield random() * value
