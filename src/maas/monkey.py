# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Patch django to work with twisted for MAAS."""

__all__ = [
    "patch_get_script_prefix",
]


def patch_get_script_prefix():
    """Patch internal django _prefixes to a global.

    Django sets up the _prefixes as a thread.local(). This causes an issue with
    twisted or any other thread, as it does not get the correct prefix when
    using reverse. This converts the local() into an object that is global.
    """
    from django.core import urlresolvers
    urlresolvers._prefixes = type('', (), {})()
