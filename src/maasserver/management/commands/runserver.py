# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: run the server.  Overrides the default implementation."""

from socketserver import ThreadingMixIn

from django.core.management.commands.runserver import BaseRunserverCommand
from django.core.servers import basehttp
from django.core.servers.basehttp import WSGIServer

from maasserver.start_up import start_up


class Command(BaseRunserverCommand):
    """Customized "runserver" command that wraps the WSGI handler."""

    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument(
            "--threading",
            action="store_true",
            dest="use_threading",
            default=False,
            help="Use threading for web server.",
        )

    def run(self, *args, **options):
        threading = options.get("use_threading", False)
        if threading:
            # This is a simple backport from Django's future
            # version to support threading.
            class ThreadedWSGIServer(ThreadingMixIn, WSGIServer):
                pass

            # Monkey patch basehttp.WSGIServer.
            setattr(basehttp, "WSGIServer", ThreadedWSGIServer)  # noqa: B010

        start_up()
        return super().run(*args, **options)
