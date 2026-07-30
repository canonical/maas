# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handler for permanently removed endpoints (HTTP 410 Gone).

The KVM/VM host, pod and VM cluster handlers are kept for
backwards-compatibility but every operation responds with HTTP 410 Gone. This
module centralises the message and the helper used to raise it.
"""

from maasserver.exceptions import MAASAPIGone

VMHOST_REMOVED_MESSAGE = "VM host (KVM) support has been removed from MAAS."


def vmhost_gone(*args, **kwargs):
    """Raise ``MAASAPIGone`` for any removed VM host endpoint."""
    raise MAASAPIGone(VMHOST_REMOVED_MESSAGE)
