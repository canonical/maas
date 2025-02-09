# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to PodHints changes."""

from django.db.models.signals import m2m_changed

from maasserver.models import PodHints
from maasserver.utils.signals import SignalsManager

signals = SignalsManager()


def pod_nodes_changed(
    sender, instance, action, reverse, model, pk_set, **kwargs
):
    if action == "post_remove":
        # Recalculate resources based on the remaining Nodes.
        instance.pod.sync_hints_from_nodes()


signals.watch(m2m_changed, pod_nodes_changed, sender=PodHints.nodes.through)


# Enable all signals by default
signals.enable()
