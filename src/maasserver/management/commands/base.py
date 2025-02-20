#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from django.core.management import BaseCommand

from maasserver.sqlalchemy import service_layer
from maasserver.utils.orm import with_connection


class BaseCommandWithConnection(BaseCommand):
    """
    A base class for executing commands that require a database connection.

    This class ensures that the service layer is properly initialized before execution
    and safely closed afterward.
    """

    @with_connection
    def execute(self, *args, **options):
        try:
            service_layer.init()
            return super().execute(*args, **options)
        finally:
            service_layer.close()
