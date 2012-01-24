# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django PRODUCTION settings for maas project."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maas.settings import *

# Location where python-oops should store errors.
OOPS_REPOSITORY = '/var/log/maas'
