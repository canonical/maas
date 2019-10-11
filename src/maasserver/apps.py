# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.apps import AppConfig


class MAASConfig(AppConfig):
    name = "maasserver"
    verbose_name = "MAAS regiond"

    def ready(self):
        """Patch Django now that is configured."""
        from maasserver.monkey import add_patches

        add_patches()
