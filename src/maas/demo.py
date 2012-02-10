# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django DEMO settings for maas project."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type

# SKIP, developement settings should override base settings.
from maas.settings import *
from maas.development import *

# This should match the setting in Makefile:pserv.pid.
PSERV_URL = "http://localhost:8001/api"
