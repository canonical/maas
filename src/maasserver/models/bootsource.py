# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for a source of boot resources."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'BootSource',
    ]


from django.core.exceptions import ValidationError
from django.db.models import (
    FilePathField,
    URLField,
)
from django.db.models.signals import post_save
from maasserver import DefaultMeta
from maasserver.fields import EditableBinaryField
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


class BootSource(CleanSave, TimestampedModel):
    """A source for boot resources."""

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    url = URLField(
        blank=False, unique=True, help_text="The URL of the BootSource.")

    keyring_filename = FilePathField(
        blank=True,
        help_text="The path to the keyring file for this BootSource.")

    keyring_data = EditableBinaryField(
        blank=True,
        help_text="The GPG keyring for this BootSource, as a binary blob.")

    def clean(self, *args, **kwargs):
        super(BootSource, self).clean(*args, **kwargs)

        # You have to specify one of {keyring_data, keyring_filename}.
        if len(self.keyring_filename) == 0 and len(self.keyring_data) == 0:
            raise ValidationError(
                "One of keyring_data or keyring_filename must be specified.")

        # You can have only one of {keyring_filename, keyring_data}; not
        # both.
        if len(self.keyring_filename) > 0 and len(self.keyring_data) > 0:
            raise ValidationError(
                "Only one of keyring_filename or keyring_data can be "
                "specified.")

    def to_dict_without_selections(self):
        """Return the current `BootSource` as a dict, without including any
        `BootSourceSelection` items.

        The dict will contain the details of the `BootSource`.

        If the `BootSource` has keyring_data, that data will be returned
        base64 encoded. Otherwise the `BootSource` will have a value in
        its keyring_filename field, and that file's contents will be
        base64 encoded and returned.
        """
        if len(self.keyring_data) > 0:
            keyring_data = self.keyring_data
        else:
            with open(self.keyring_filename, 'rb') as keyring_file:
                keyring_data = keyring_file.read()
        return {
            "url": self.url,
            "keyring_data": bytes(keyring_data),
            "selections": [],
            }

    def to_dict(self):
        """Return the current `BootSource` as a dict.

        The dict will contain the details of the `BootSource` and all
        its `BootSourceSelection` items.

        If the `BootSource` has keyring_data, that data will be returned
        base64 encoded. Otherwise the `BootSource` will have a value in
        its keyring_filename field, and that file's contents will be
        base64 encoded and returned.
        """
        data = self.to_dict_without_selections()
        data['selections'] = [
            selection.to_dict()
            for selection in self.bootsourceselection_set.all()
            ]
        return data


def update_boot_source_cache(sender, instance, **kwargs):
    """Update the `BootSourceCache` with information for the updated
    source."""
    # Avoid circular import
    from maasserver.bootsources import cache_boot_sources_in_thread
    cache_boot_sources_in_thread()

post_save.connect(update_boot_source_cache, BootSource)
