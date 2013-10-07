# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: write the MAAS named zone files.

If any of the cluster controllers connected to this MAAS region controller
is configured to manage DNS, write the DNS configuration.

The main purpose of this command is for it to be run when 'maas-dns' is
installed.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'Command',
    ]

from django.core.management.base import BaseCommand
from maasserver.dns import write_full_dns_config


class Command(BaseCommand):
    help = (
        "Write the DNS configuration files and reload the DNS server if "
        "this region has cluster controllers configured to manage DNS.")

    def handle(self, *args, **options):
        write_full_dns_config()
