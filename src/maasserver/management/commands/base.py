# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.core.management import BaseCommand


class BaseCommandWithConnection(BaseCommand):
    """
    A base class for executing commands that require a database connection.

    This class ensures that the service layer is properly initialized before execution
    and safely closed afterward.
    """

    def execute(self, *args, **options):
        # Delay the import of with_connection to reduce startup overhead for commands when the parser is built.
        from maasserver.utils.orm import with_connection

        @with_connection
        def _execute():
            from maasserver.sqlalchemy import service_layer

            try:
                service_layer.init()
                return super(BaseCommandWithConnection, self).execute(
                    *args, **options
                )
            finally:
                service_layer.close()

        return _execute()
