# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MaaS Server application."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maasserver import provisioning

# This has been imported so that it can register its signal handlers early on,
# before it misses anything. (Mentioned below to silence lint warnings.)
provisioning
