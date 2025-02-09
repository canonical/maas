# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to DHCPSnippet changes."""

from django.db.models.signals import post_delete

from maasserver.models import DHCPSnippet
from maasserver.utils.signals import SignalsManager

signals = SignalsManager()


def post_delete_dhcp_snippet_clean_values(sender, instance, **kwargs):
    """Removes the just-deleted DHCPSnippet's set of values."""
    for value in instance.value.previous_versions():
        value.delete()


signals.watch(
    post_delete, post_delete_dhcp_snippet_clean_values, sender=DHCPSnippet
)

# Enable all signals by default.
signals.enable()
