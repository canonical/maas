# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.shortcuts import redirect

from maasserver.api.support import AnonymousOperationsHandler


class MAASRunScriptHandler(AnonymousOperationsHandler):
    def read(self, request, architecture):
        return redirect(f"/MAAS/hardware-sync/{architecture}")
