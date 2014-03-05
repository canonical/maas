# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Describe the architectures which a cluster controller supports."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'list_supported_architectures',
    ]


# Hard-coded architectures list in initial implementation.
# XXX jtv 2014-03-05: Let hardware drivers decide this, e.g. based on boot
# images available upstream.
ARCHITECTURES = ['i386/generic', 'amd64/generic', 'armhf/highbank']


def list_supported_architectures():
    """List all architectures supported by this cluster controller.

    These are all architectures that the cluster controller could conceivably
    deal with, regardless of whether the controller has images for them.

    Result is sorted lexicographically.
    """
    # XXX jtv 2014-03-05: Move into hardware driver, and query through RPC.
    return sorted(ARCHITECTURES)
