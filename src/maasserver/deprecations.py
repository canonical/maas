# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasserver.utils.orm import postgresql_major_version
from provisioningserver.logger import LegacyLogger

DEPRECATION_URL = "https://maas.io/deprecations/{id}"


class Deprecation:
    """A deprecation notice."""

    def __init__(self, id, since, description, link_text=""):
        self.id = id
        self.since = since
        self.description = description
        self.link_text = link_text

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
    "POSTGRES_OLDER_THAN_14": Deprecation(
        id="MD3",
        since="3.3",
        description="The PostgreSQL version in use is older than 14.",
        link_text="How to upgrade the PostgreSQL server",
    )
}


def get_deprecations():
    """Return a list of currently active deprecation notices."""

    deprecations = []
    if postgresql_major_version() < 14:
        deprecations.append(DEPRECATIONS["POSTGRES_OLDER_THAN_14"])
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
                dismissable=False,
                **{kind: True},
            ).save()

    # delete other deprecation notifications
    if notifications:
        Notification.objects.filter(ident__in=notifications).delete()
