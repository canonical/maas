# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
"""Hardening validation lifecycle for the region controller.

:func:`sync_hardening_notifications` is called from ``inner_start_up`` to
post/clear non-dismissable ``error``
:class:`~maasserver.models.Notification`\\s keyed by a stable ``ident``,
reusing the certificate-expiration pattern.
"""

import logging

from maasserver.models import Notification
from maasserver.utils.orm import transactional

_log = logging.getLogger("maas.hardening")

HARDENING_NOTIFICATION_IDENT_PREFIX = "hardening-"
HARDENING_CTRL_IDENT_PREFIX = "hardening-ctrl-"


@transactional
def sync_hardening_notifications(
    violations: list, controller_id: str | None = None
) -> None:
    """Post/clear hardening Notifications based on *violations*.

    For every active violation, upsert an admin-targeted, non-dismissable
    ``error`` Notification.  Stale hardening Notifications are deleted.

    Bind-related violations (``"bind" in config_key``) are scoped to
    *controller_id* when supplied, so each region controller in an HA setup
    has its own notification and the message names the affected host.
    Non-bind violations remain global.  Safe to call with an empty list.
    """
    # Build {ident: (v, message, context)} in one pass so we have
    # active_idents before touching the DB.
    pending: dict[str, tuple] = {}
    for v in violations:
        if controller_id and "bind" in v.config_key:
            # config_key as suffix keeps idents within the 40-char field limit.
            ident = (
                f"{HARDENING_CTRL_IDENT_PREFIX}{controller_id}-{v.config_key}"
            )
            message = f"[{controller_id}] {v.message} {v.resolution}"
            context = {
                "code": v.code,
                "config_key": v.config_key,
                "file_path": v.file_path,
                "controller_id": controller_id,
            }
        else:
            ident = v.ident
            message = f"{v.message} {v.resolution}"
            context = {
                "code": v.code,
                "config_key": v.config_key,
                "file_path": v.file_path,
            }
        pending[ident] = (v, message, context)

    # Remove stale global (non-controller-scoped) hardening notifications.
    Notification.objects.filter(
        ident__startswith=HARDENING_NOTIFICATION_IDENT_PREFIX,
    ).exclude(
        ident__startswith=HARDENING_CTRL_IDENT_PREFIX,
    ).exclude(ident__in=pending).delete()

    # Remove stale notifications for this controller only.
    if controller_id:
        Notification.objects.filter(
            ident__startswith=f"{HARDENING_CTRL_IDENT_PREFIX}{controller_id}-",
        ).exclude(ident__in=pending).delete()

    for ident, (v, message, context) in pending.items():
        Notification.objects.update_or_create(
            ident=ident,
            defaults={
                "category": "error",
                "admins": True,
                "users": False,
                "dismissable": False,
                "message": message,
                "context": context,
            },
        )
        _log.info(
            "hardening_notification_posted: ident=%s code=%s controller_id=%s",
            ident,
            v.code,
            controller_id,
        )
