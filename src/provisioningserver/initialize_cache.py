# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Module with side effect: import to initialize the inter-worker cache.

This is here merely so as to avoid accidental initialization of the cache.
Import this module and the cache will be initialized.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from provisioningserver.cache import initialize


initialize()
