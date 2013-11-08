# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: set up the MAAS named configuration.

This creates a basic, blank DNS configuration which will allow MAAS to
reload its configuration once zone files will be written.

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

from optparse import make_option

from django.core.management.base import BaseCommand
from maasserver.models import Config
from provisioningserver.dns.config import (
    DNSConfig,
    set_up_options_conf,
    setup_rndc,
    )


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option(
            '--no-clobber', dest='no_clobber', action='store_true',
            default=False,
            help=(
                "Don't overwrite the configuration file if it already "
                "exists.")),
    )
    help = (
        "Set up MAAS DNS configuration: a blank configuration and "
        "all the RNDC configuration options allowing MAAS to reload "
        "BIND once zones configuration files will be written.")

    def handle(self, *args, **options):
        no_clobber = options.get('no_clobber')
        setup_rndc()
        upstream_dns = Config.objects.get_config("upstream_dns")
        set_up_options_conf(
            overwrite=not no_clobber, upstream_dns=upstream_dns)
        config = DNSConfig()
        config.write_config(
            overwrite=not no_clobber, zone_names=(), reverse_zone_names=())
