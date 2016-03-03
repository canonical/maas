# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Forms relating to filesystems."""

__all__ = [
    "MountFilesystemForm",
]

from typing import Optional

from django.forms import Form
from maasserver.fields import StrippedCharField
from maasserver.forms import AbsolutePathField
from maasserver.models import Filesystem
from provisioningserver.utils import typed


class MountFilesystemForm(Form):
    """Form used to mount a filesystem."""

    @typed
    def __init__(self, filesystem: Optional[Filesystem], *args, **kwargs):
        super(MountFilesystemForm, self).__init__(*args, **kwargs)
        self.filesystem = filesystem
        self.setup()

    def setup(self):
        if self.filesystem is not None:
            if self.filesystem.uses_mount_point:
                self.fields["mount_point"] = AbsolutePathField(required=True)
            self.fields["mount_options"] = StrippedCharField(required=False)

    def clean(self):
        cleaned_data = super(MountFilesystemForm, self).clean()
        if self.filesystem is None:
            self.add_error(
                None, "Cannot mount an unformatted partition "
                "or block device.")
        elif self.filesystem.filesystem_group is not None:
            self.add_error(
                None, "Filesystem is part of a filesystem group, "
                "and cannot be mounted.")
        return cleaned_data

    def save(self):
        if "mount_point" in self.cleaned_data:
            self.filesystem.mount_point = self.cleaned_data['mount_point']
        else:
            self.filesystem.mount_point = "none"  # e.g. for swap.
        if "mount_options" in self.cleaned_data:
            self.filesystem.mount_options = self.cleaned_data['mount_options']
        self.filesystem.save()
