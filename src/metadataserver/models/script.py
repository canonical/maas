# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = [
    "Script",
]

import datetime

from django.contrib.postgres.fields import ArrayField
from django.db.models import (
    BooleanField,
    CASCADE,
    CharField,
    DurationField,
    IntegerField,
    Manager,
    OneToOneField,
    TextField,
)
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.models.versionedtextfile import VersionedTextFile
from metadataserver import DefaultMeta
from metadataserver.enum import (
    SCRIPT_TYPE,
    SCRIPT_TYPE_CHOICES,
)


class ScriptManager(Manager):

    def create(self, *, script=None, timeout=None, **kwargs):
        """Create a Script.

        This is a modified version of Django's create method for use with
        Scripts. If 'script' is a string a VersionedTextFile will be
        automatically created for it. If timeout is an int a timedelta will be
        automatically created.
        """
        if script is not None and not isinstance(script, VersionedTextFile):
            script = VersionedTextFile.objects.create(data=script)

        if timeout is not None:
            if isinstance(timeout, datetime.timedelta):
                kwargs['timeout'] = timeout
            else:
                kwargs['timeout'] = datetime.timedelta(seconds=timeout)

        return super().create(script=script, **kwargs)


class Script(CleanSave, TimestampedModel):

    # Force model into the metadataserver namespace.
    class Meta(DefaultMeta):
        pass

    objects = ScriptManager()

    name = CharField(max_length=255, unique=True)

    title = CharField(max_length=255, blank=True)

    description = TextField(blank=True)

    tags = ArrayField(TextField(), blank=True, null=True, default=list)

    script_type = IntegerField(
        choices=SCRIPT_TYPE_CHOICES, default=SCRIPT_TYPE.TESTING)

    # 0 is no timeout
    timeout = DurationField(default=datetime.timedelta())

    destructive = BooleanField(default=False)

    # True only if the script is shipped with MAAS
    default = BooleanField(default=False)

    script = OneToOneField(VersionedTextFile, on_delete=CASCADE)

    def __str__(self):
        return self.name

    def add_tag(self, tag):
        """Add tag to Script."""
        if tag not in self.tags:
            self.tags.append(tag)

    def remove_tag(self, tag):
        """Remove tag from Script."""
        if tag in self.tags:
            self.tags.remove(tag)
