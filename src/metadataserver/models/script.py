# Copyright 2017-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = [
    "Script",
    "translate_hardware_type",
    "translate_script_parallel",
    "translate_script_type",
]

from collections import namedtuple
import datetime

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db.models import (
    BooleanField,
    CASCADE,
    CharField,
    DurationField,
    IntegerField,
    JSONField,
    Manager,
    OneToOneField,
    TextField,
)

from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.models.versionedtextfile import VersionedTextFile
from metadataserver.enum import (
    HARDWARE_TYPE,
    HARDWARE_TYPE_CHOICES,
    SCRIPT_PARALLEL,
    SCRIPT_PARALLEL_CHOICES,
    SCRIPT_TYPE,
    SCRIPT_TYPE_CHOICES,
)

ForHardware = namedtuple("ForHardware", ("modaliases", "pci", "usb"))


def translate_script_type(script_type):
    if isinstance(script_type, int) or script_type.isdigit():
        ret = int(script_type)
        for script_type_id, _ in SCRIPT_TYPE_CHOICES:
            if ret == script_type_id:
                return ret
        raise ValidationError("Invalid script type numeric value.")
    elif script_type in ["test", "testing"]:
        return SCRIPT_TYPE.TESTING
    elif script_type in ["commission", "commissioning"]:
        return SCRIPT_TYPE.COMMISSIONING
    else:
        raise ValidationError("Script type must be testing or commissioning")


def translate_hardware_type(hardware_type):
    if isinstance(hardware_type, int) or hardware_type.isdigit():
        ret = int(hardware_type)
        for hardware_type_id, _ in HARDWARE_TYPE_CHOICES:
            if ret == hardware_type_id:
                return ret
        raise ValidationError("Invalid hardware type numeric value.")

    hardware_type = hardware_type.lower()

    if hardware_type in [
        "node",
        "machine",
        "controller",
        "other",
        "generic",
    ]:
        return HARDWARE_TYPE.NODE
    elif hardware_type in ["cpu", "processor"]:
        return HARDWARE_TYPE.CPU
    elif hardware_type in ["memory", "ram"]:
        return HARDWARE_TYPE.MEMORY
    elif hardware_type in ["storage", "disk", "ssd"]:
        return HARDWARE_TYPE.STORAGE
    elif hardware_type in ["network", "net", "interface"]:
        return HARDWARE_TYPE.NETWORK
    elif hardware_type in ["gpu", "graphics"]:
        return HARDWARE_TYPE.GPU
    else:
        raise ValidationError(
            "Hardware type must be node, cpu, memory, storage, or gpu"
        )


def translate_script_parallel(parallel):
    if isinstance(parallel, int) or parallel.isdigit():
        ret = int(parallel)
        for script_parallel_id, _ in SCRIPT_PARALLEL_CHOICES:
            if ret == script_parallel_id:
                return ret
        raise ValidationError("Invalid script parallel numeric value.")
    elif parallel in ["disabled", "none"]:
        return SCRIPT_PARALLEL.DISABLED
    elif parallel in ["instance", "name"]:
        return SCRIPT_PARALLEL.INSTANCE
    elif parallel in ["any", "enabled"]:
        return SCRIPT_PARALLEL.ANY
    else:
        raise ValidationError(
            "Script parallel must be disabled, instance, or any."
        )


class ScriptManager(Manager):
    def create(self, *, script=None, timeout=None, comment=None, **kwargs):
        """Create a Script.

        This is a modified version of Django's create method for use with
        Scripts. If 'script' is a string a VersionedTextFile will be
        automatically created for it. If timeout is an int a timedelta will be
        automatically created.
        """
        if script is not None and not isinstance(script, VersionedTextFile):
            script = VersionedTextFile.objects.create(
                data=script, comment=comment
            )

        if timeout is not None:
            if isinstance(timeout, datetime.timedelta):
                kwargs["timeout"] = timeout
            else:
                kwargs["timeout"] = datetime.timedelta(seconds=timeout)

        return super().create(script=script, **kwargs)


class Script(CleanSave, TimestampedModel):

    objects = ScriptManager()

    name = CharField(max_length=255, unique=True)

    title = CharField(max_length=255, blank=True)

    description = TextField(blank=True)

    tags = ArrayField(TextField(), blank=True, null=True, default=list)

    script_type = IntegerField(
        choices=SCRIPT_TYPE_CHOICES, default=SCRIPT_TYPE.TESTING
    )

    # The hardware the script configures or tests.
    hardware_type = IntegerField(
        choices=HARDWARE_TYPE_CHOICES, default=HARDWARE_TYPE.NODE
    )

    # Whether the script can run in parallel with other scripts.
    parallel = IntegerField(
        choices=SCRIPT_PARALLEL_CHOICES, default=SCRIPT_PARALLEL.DISABLED
    )

    # Any results which will be made availble after the script is run.
    results = JSONField(blank=True, default=dict)

    # Parameters which may be passed to the script and their constraints.
    parameters = JSONField(blank=True, default=dict)

    # apt, snap, dpkg, to install or archives to extract.
    packages = JSONField(blank=True, default=dict)

    # 0 is no timeout
    timeout = DurationField(default=datetime.timedelta())

    destructive = BooleanField(default=False)

    # True only if the script is shipped with MAAS
    default = BooleanField(default=False)

    script = OneToOneField(VersionedTextFile, on_delete=CASCADE)

    # A list of hardware identifiers(modalias, PCI id, USB id, or name) this
    # script is applicable to. This script will always run on machines with
    # matching hardware.
    for_hardware = ArrayField(
        CharField(max_length=255), blank=True, default=list
    )

    # Whether or not the script may reboot while running. Tells the status
    # monitor to wait until NODE_FAILURE_MONITORED_STATUS_TIMEOUTS before
    # timing out.
    may_reboot = BooleanField(default=False)

    # Only applicable to commissioning scripts. When true reruns commissioning
    # scripts after receiving the result.
    recommission = BooleanField(default=False)

    # Whether or not maas-run-remote-scripts should apply user configured
    # network settings before running the Script.
    apply_configured_networking = BooleanField(default=False)

    @property
    def ForHardware(self):
        """Parses the for_hardware field and returns a ForHardware tuple."""
        modaliases = []
        pci = []
        usb = []
        for descriptor in self.for_hardware:
            try:
                hwtype, value = descriptor.split(":", 1)
            except ValueError:
                continue
            if hwtype == "modalias":
                modaliases.append(value)
            elif hwtype == "pci":
                pci.append(value)
            elif hwtype == "usb":
                usb.append(value)
        return ForHardware(modaliases, pci, usb)

    @property
    def script_type_name(self):
        for script_type, script_type_name in SCRIPT_TYPE_CHOICES:
            if self.script_type == script_type:
                return script_type_name
        return "unknown"

    @property
    def hardware_type_name(self):
        return HARDWARE_TYPE_CHOICES[self.hardware_type][1]

    @property
    def parallel_name(self):
        return SCRIPT_PARALLEL_CHOICES[self.parallel][1]

    def __str__(self):
        return self.name

    def add_tag(self, tag):
        """Add tag to Script."""
        if tag not in self.tags:
            self.tags = self.tags + [tag]

    def remove_tag(self, tag):
        """Remove tag from Script."""
        if tag in self.tags:
            tags = self.tags.copy()
            tags.remove(tag)
            self.tags = tags

    def save(self, *args, **kwargs):
        if self.destructive:
            self.add_tag("destructive")
        else:
            self.remove_tag("destructive")

        for hw_type, hw_type_label in HARDWARE_TYPE_CHOICES:
            if hw_type == self.hardware_type:
                self.add_tag(hw_type_label.lower())
            else:
                self.remove_tag(hw_type_label.lower())

        return super().save(*args, **kwargs)
