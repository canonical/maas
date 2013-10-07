# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing facilities for API credentials."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'make_api_credentials',
    ]

from maastesting.factory import factory


def make_api_credentials():
    """Create a tuple of fake API credentials."""
    return (
        factory.make_name('consumer-key'),
        factory.make_name('resource-token'),
        factory.make_name('resource-secret'),
        )
