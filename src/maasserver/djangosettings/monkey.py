# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Patch django to work with twisted for MAAS."""


def patch_get_script_prefix():
    """Patch internal django _prefixes to a global.

    Django sets up the _prefixes as a thread.local(). This causes an issue with
    twisted or any other thread, as it does not get the correct prefix when
    using reverse. This converts the local() into an object that is global.
    """
    from django.urls import base

    unset = object()
    value = getattr(base._prefixes, "value", unset)
    base._prefixes = type("", (), {})()
    if value is not unset:
        base._prefixes.value = value
