# Copyright 2017-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.db.models import DateTimeField, TextField
from django.utils.timezone import now

from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


class PerfTestBuild(CleanSave, TimestampedModel):
    start_ts = DateTimeField(default=now)
    end_ts = DateTimeField(blank=True, null=True)
    git_branch = TextField()
    git_hash = TextField(unique=True)
    release = TextField(blank=True, null=True)
