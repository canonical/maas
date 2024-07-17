# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from collections import Counter
from datetime import datetime
from enum import Enum
import re
from typing import List, NamedTuple, Optional

from django.db.models import (
    BooleanField,
    CASCADE,
    CharField,
    Count,
    DateTimeField,
    Manager,
    OneToOneField,
    Q,
)

from maasserver.models.cleansave import CleanSave
from maasserver.models.node import Node
from maasserver.models.notification import Notification
from maasserver.models.timestampedmodel import TimestampedModel
from provisioningserver.enum import (
    CONTROLLER_INSTALL_TYPE,
    CONTROLLER_INSTALL_TYPE_CHOICES,
)
from provisioningserver.utils.snap import SnapChannel
from provisioningserver.utils.version import MAASVersion

PPA_URL_RE = re.compile(
    r"http://ppa.launchpad.net/(?P<ppa>\w+/[\w\.]+)/ubuntu/ (?P<release>\w+)/main$"
)


class TargetVersion(NamedTuple):
    """The target version for the MAAS deployment."""

    version: MAASVersion
    snap_channel: SnapChannel
    snap_cohort: str = ""
    first_reported: Optional[datetime] = None


class VERSION_ISSUES(Enum):
    """Possible issues with a controller version with regards to target version."""

    DIFFERENT_CHANNEL = "different-channel"
    DIFFERENT_COHORT = "different-cohort"
    MISSING_CHANNEL = "missing-channel"


class ControllerInfoManager(Manager):
    def set_version(self, controller, version):
        self.update_or_create(defaults={"version": version}, node=controller)

    def set_versions_info(self, controller, versions):
        details = {
            "install_type": versions.install_type,
            "version": versions.current.version,
            # initialize other fields as null in case the controller is
            # upgraded from one install type to another
            "update_version": "",
            "update_origin": "",
            "snap_cohort": "",
            "snap_revision": "",
            "snap_update_revision": "",
            "update_first_reported": None,
        }
        if versions.install_type == CONTROLLER_INSTALL_TYPE.SNAP:
            details.update(
                {
                    "snap_revision": versions.current.revision,
                    "snap_cohort": versions.cohort,
                    "update_origin": (
                        str(versions.channel) if versions.channel else ""
                    ),
                }
            )
        elif versions.install_type == CONTROLLER_INSTALL_TYPE.DEB:
            details["update_origin"] = self._parse_deb_origin(
                versions.current.origin
            )

        if versions.update:
            details.update(
                {
                    "update_version": versions.update.version,
                    "update_first_reported": datetime.now(),
                }
            )
            if versions.install_type == CONTROLLER_INSTALL_TYPE.DEB:
                # override the update origin as it might be different from the
                # installed one
                details["update_origin"] = self._parse_deb_origin(
                    versions.update.origin
                )
            elif versions.install_type == CONTROLLER_INSTALL_TYPE.SNAP:
                details["snap_update_revision"] = versions.update.revision

        info, created = self.get_or_create(defaults=details, node=controller)
        if created:
            return

        if versions.update:
            if (
                versions.update.version == info.update_version
                and versions.install_type == info.install_type
            ):
                # if the version is the same but the install type has changed,
                # still update the first reported time
                del details["update_first_reported"]

        for key, value in details.items():
            setattr(info, key, value)
        info.save()

    def _parse_deb_origin(self, origin):
        match = PPA_URL_RE.match(origin)
        if match:
            return f"ppa:{match['ppa']}"
        return origin


class ControllerInfo(CleanSave, TimestampedModel):
    """Metadata about a node that is a controller."""

    class Meta:
        verbose_name = "ControllerInfo"

    objects = ControllerInfoManager()

    node = OneToOneField(
        Node, null=False, blank=False, on_delete=CASCADE, primary_key=True
    )

    version = CharField(max_length=255, blank=True, default="")
    update_version = CharField(max_length=255, blank=True, default="")
    # the snap channel or deb repo for the update
    update_origin = CharField(max_length=255, blank=True, default="")
    update_first_reported = DateTimeField(blank=True, null=True)
    install_type = CharField(
        max_length=255,
        blank=True,
        choices=CONTROLLER_INSTALL_TYPE_CHOICES,
        default=CONTROLLER_INSTALL_TYPE.UNKNOWN,
    )
    snap_cohort = CharField(max_length=255, blank=True, default="")
    snap_revision = CharField(max_length=255, blank=True, default="")
    snap_update_revision = CharField(max_length=255, blank=True, default="")
    vault_configured = BooleanField(default=False)

    def __str__(self):
        return f"{self.__class__.__name__} ({self.node.hostname})"

    def is_up_to_date(self, target_version: TargetVersion) -> bool:
        """Return whether the controller is up-to-date with the target version."""
        return (
            not self.update_version
            and MAASVersion.from_string(self.version) == target_version.version
        )

    def get_version_issues(self, target: TargetVersion) -> List[str]:
        """Return a list of version-related issues compared to the target version."""
        issues = []
        if self.install_type == CONTROLLER_INSTALL_TYPE.SNAP:
            if self.update_origin:
                snap_channel = SnapChannel.from_string(self.update_origin)
            else:
                snap_channel = None
                issues.append(VERSION_ISSUES.MISSING_CHANNEL.value)

            if snap_channel and snap_channel != target.snap_channel:
                issues.append(VERSION_ISSUES.DIFFERENT_CHANNEL.value)
            if self.snap_cohort != target.snap_cohort:
                issues.append(VERSION_ISSUES.DIFFERENT_COHORT.value)
        return issues


def get_maas_version() -> Optional[MAASVersion]:
    """Return the version for the deployment.

    The returned version is the short version (up to the qualifier, if any)
    used by the most controllers.

    """
    version_data = (
        ControllerInfo.objects.exclude(version="")
        .values_list("version")
        .annotate(count=Count("node_id"))
    )
    versions = Counter()
    for version, count in version_data:
        versions[MAASVersion.from_string(version).main_version] += count
    # sort versions by the highest count first, and highest version in case of
    # equal count
    versions = sorted(
        ((count, version) for version, count in versions.items()), reverse=True
    )
    if not versions:
        return None
    return versions[0][1]


def channel_from_version(version) -> SnapChannel:
    """channel from version constructs a SnapChannel from a MAAS version"""
    risk_map = {"alpha": "edge", "beta": "beta", "rc": "candidate"}
    risk = risk_map.get(version.qualifier_type, "stable")
    return SnapChannel(
        track=f"{version.major}.{version.minor}",
        risk=risk,
    )


def get_target_version() -> Optional[TargetVersion]:
    """Get the target version for the deployment."""
    highest_version = None
    highest_update = None
    update_first_reported = None
    for info in ControllerInfo.objects.exclude(version=""):
        version = MAASVersion.from_string(info.version)
        highest_version = (
            max((highest_version, version)) if highest_version else version
        )

        if not info.update_version:
            continue

        update = MAASVersion.from_string(info.update_version)
        if not highest_update:
            highest_update = update
            update_first_reported = info.update_first_reported
        elif update < highest_update:
            continue
        elif update > highest_update:
            highest_update = update
            update_first_reported = info.update_first_reported
        else:  # same version
            update_first_reported = min(
                (update_first_reported, info.update_first_reported)
            )

    if highest_update and highest_update > highest_version:
        version = highest_update
    else:
        # don't report any update
        version = highest_version
        update_first_reported = None

    if version is None:
        return None

    def field_for_snap_controllers(field, version):
        version = str(version)
        return list(
            ControllerInfo.objects.filter(
                Q(version=version) | Q(update_version=version),
                install_type=CONTROLLER_INSTALL_TYPE.SNAP,
            )
            .exclude(**{field: ""})
            .values_list(field, flat=True)
            .distinct()
        )

    channels = field_for_snap_controllers("update_origin", version)
    snap_channel = None
    if channels:
        # report the minimum (with lowest risk) channel that sees the target
        # version
        for channel in channels:
            channel = SnapChannel.from_string(channel)
            if not channel.is_release_branch():
                # only point to a branch if it's a release one, as other branches
                # are in general intended as a temporary change for testing
                channel.branch = ""
            snap_channel = (
                min(channel, snap_channel) if snap_channel else channel
            )
    else:
        # compose the channel from the target version
        snap_channel = channel_from_version(version)

    # report a cohort only if all controllers with the target version are on
    # the same cohort (or have no cohort)
    cohorts = field_for_snap_controllers("snap_cohort", version)
    snap_cohort = cohorts[0] if len(cohorts) == 1 else ""

    return TargetVersion(
        version,
        snap_channel,
        snap_cohort=snap_cohort,
        first_reported=update_first_reported,
    )


UPGRADE_ISSUE_NOTIFICATION_IDENT = "upgrade_version_issue"
UPGRADE_STATUS_NOTIFICATION_IDENT = "upgrade_status"


def update_version_notifications():
    _process_udpate_issues_notification()
    _process_update_status_notification()


def _process_udpate_issues_notification():
    info = ControllerInfo.objects
    multiple_install_types = info.values("install_type").distinct().count() > 1
    multiple_origins = info.values("update_origin").distinct().count() > 1
    multiple_cohorts = info.values("snap_cohort").distinct().count() > 1
    # note that `version` and `update_version` are compared here as strings
    # from the database. It's possible the same effective version is reported
    # as different strings because of deb epoch, but it doesn't really matter
    # in this case as other discrepancies would trigger the "different
    # installation sources" notification before
    multiple_versions = info.values("version").distinct().count() > 1
    multiple_upgrade_versions = (
        info.exclude(update_version="")
        .values("update_version")
        .distinct()
        .count()
        > 1
    )

    def set_warning(reason, message):
        defaults = {
            "category": "warning",
            "admins": True,
            "message": f"{message}. <a href='/MAAS/r/controllers'>Review controllers.</a>",
            "context": {"reason": reason},
        }
        notification, created = Notification.objects.get_or_create(
            ident=UPGRADE_ISSUE_NOTIFICATION_IDENT,
            defaults=defaults,
        )
        if not created and notification.context["reason"] != reason:
            # create a new notification so that it shows even if users have
            # dismissed the previous one
            notification.delete()
            Notification.objects.create(
                ident=UPGRADE_ISSUE_NOTIFICATION_IDENT, **defaults
            )

    if any((multiple_install_types, multiple_origins, multiple_cohorts)):
        set_warning(
            "install_source", "Controllers have different installation sources"
        )
    elif multiple_upgrade_versions:
        set_warning(
            "upgrade_versions", "Controllers report different upgrade versions"
        )
    elif multiple_versions:
        set_warning("versions", "Controllers have different versions")
    else:
        Notification.objects.filter(
            ident=UPGRADE_ISSUE_NOTIFICATION_IDENT
        ).delete()


def _process_update_status_notification():
    def set_update_notification(version, completed):
        context = {"version": str(version)}
        if completed:
            message = "MAAS has been updated to version {version}."
            context["status"] = "completed"
        else:
            message = (
                "MAAS {version} is available, controllers will upgrade soon."
            )
            context["status"] = "inprogress"

        defaults = {
            "category": "success" if completed else "info",
            "admins": True,
            "message": message,
            "context": context,
        }
        return Notification.objects.get_or_create(
            ident=UPGRADE_STATUS_NOTIFICATION_IDENT,
            defaults=defaults,
        )

    target_version = get_target_version()
    state_notification = Notification.objects.filter(
        ident=UPGRADE_STATUS_NOTIFICATION_IDENT
    ).first()
    if target_version and target_version.first_reported:
        # an update is available
        update_version = target_version.version.main_version
        if state_notification:
            notification_version = MAASVersion.from_string(
                state_notification.context["version"]
            )
            if notification_version < update_version:
                # replace old notification with the new one
                state_notification.delete()
        set_update_notification(update_version, completed=False)
    elif state_notification:
        # no update but there's a previous notification
        current_version = get_maas_version().main_version
        notification_version = MAASVersion.from_string(
            state_notification.context["version"]
        )
        if (
            state_notification.context["status"] == "completed"
            and notification_version == current_version
        ):
            return
        state_notification.delete()
        set_update_notification(current_version, completed=True)
