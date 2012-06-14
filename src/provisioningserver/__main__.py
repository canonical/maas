#!/usr/bin/env python2.7
# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Command-line interface for the MAAS provisioning component."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type

import provisioningserver.dhcp.writer
from provisioningserver.utils import ActionScript


main = ActionScript(__doc__)
main.register(
    "generate-dhcp-config",
    provisioningserver.dhcp.writer)
main()
