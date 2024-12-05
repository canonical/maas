# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasserver.models.controllerinfo import get_maas_version
from maasserver.utils.orm import get_database_owner, postgresql_major_version
from provisioningserver.logger import LegacyLogger

DEPRECATION_URL = "https://maas.io/deprecations/{id}"


class Deprecation:
    """A deprecation notice."""

    def __init__(
        self, id, since, description, link_text="", dismissable=False
    ):
        self.id = id
        self.since = since
        self.description = description
        self.link_text = link_text
        self.dismissable = dismissable

    @property
    def url(self):
        return DEPRECATION_URL.format(id=self.id)

    @property
    def message(self):
        return "Deprecation {id} ({url}): {description}".format(
            id=self.id, url=self.url, description=self.description
        )


# all known deprecation notices
DEPRECATIONS = {
    "DHCP_SNIPPETS": Deprecation(
        id="MD6",
        since="3.6",
        description="DHCP snippets are deprecated and will be removed in the next major release.",
        link_text="How to replace DHCP snippets",
        dismissable=True,
    ),
    "POSTGRES_OLDER_THAN_16": Deprecation(
        id="MD5",
        since="3.6",
        description="The PostgreSQL version in use is older than 16.",
        link_text="How to upgrade the PostgreSQL server",
        dismissable=False,
    ),
    "WRONG_MAAS_DATABASE_OWNER": Deprecation(
        id="MD4",
        since="3.4",
        description="MAAS database is owned by 'postgres' user.",
        link_text="How to fix MAAS database owner",
        dismissable=False,
    ),
}


def get_deprecations():
    """Return a list of currently active deprecation notices."""

    deprecations = []
    running_maas_version = get_maas_version()
    if (
        running_maas_version
        and running_maas_version.major == 3
        and running_maas_version.minor >= 6
    ):
        deprecations.append(DEPRECATIONS["DHCP_SNIPPETS"])
    if postgresql_major_version() < 16:
        deprecations.append(DEPRECATIONS["POSTGRES_OLDER_THAN_16"])
    if get_database_owner() == "postgres":
        deprecations.append(DEPRECATIONS["WRONG_MAAS_DATABASE_OWNER"])
    return deprecations


def log_deprecations(logger=None):
    """Log active deprecations."""
    if logger is None:
        logger = LegacyLogger()
    for d in get_deprecations():
        logger.msg(d.message)


def sync_deprecation_notifications():
    from maasserver.models import Notification

    notifications = set(
        Notification.objects.filter(
            ident__startswith="deprecation_"
        ).values_list("ident", flat=True)
    )
    for deprecation in get_deprecations():
        for kind in ("users", "admins"):
            dep_ident = f"deprecation_{deprecation.id}_{kind}"
            if dep_ident in notifications:
                notifications.remove(dep_ident)
                continue
            message = deprecation.description
            if kind == "users":
                message += "<br>Please contact your MAAS administrator."
            message += (
                f"<br><a class='p-link--external' href='{deprecation.url}'>"
                f"{deprecation.link_text}...</a>"
            )
            Notification(
                ident=dep_ident,
                category="warning",
                message=message,
                dismissable=deprecation.dismissable,
                **{kind: True},
            ).save()

    # delete other deprecation notifications
    if notifications:
        Notification.objects.filter(ident__in=notifications).delete()
