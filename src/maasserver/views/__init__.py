# Copyright 2012-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Views."""


from django.shortcuts import redirect


def handler404(request, *args, **kwargs):
    """404 Handler, just redirects to index.

    Index is handled by the static content loaded by the twisted WebApp.
    """
    return redirect("/MAAS/")
