# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for a source of boot resources."""

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db.models import (
    BinaryField,
    BooleanField,
    CASCADE,
    CharField,
    ForeignKey,
    IntegerField,
    JSONField,
    Max,
    Model,
    URLField,
)

from maasserver.models.bootsourceselection import BootSourceSelection
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


class ImageManifest(Model):
    boot_source = ForeignKey(
        "maasserver.BootSource",
        on_delete=CASCADE,
    )

    manifest = JSONField()


class BootSource(CleanSave, TimestampedModel):
    """A source for boot resources."""

    url = URLField(
        blank=False, unique=True, help_text="The URL of the BootSource."
    )

    keyring_filename = CharField(
        blank=True,
        max_length=4096,
        help_text="The path to the keyring file for this BootSource.",
    )

    keyring_data = BinaryField(
        blank=True,
        help_text="The GPG keyring for this BootSource, as a binary blob.",
        editable=True,
    )

    priority = IntegerField(
        null=False,
        validators=[MinValueValidator(0)],
        help_text="Priority value. Higher values mean higher priority. Must be non-negative.",
    )

    skip_keyring_verification = BooleanField(
        null=False,
        editable=True,
        help_text="If true, keyring signature verification will be skipped.",
    )

    def clean(self, *args, **kwargs):
        super().clean(*args, **kwargs)

        # You have to specify one of {keyring_data, keyring_filename}.
        if not self.keyring_filename and not self.keyring_data:
            raise ValidationError(
                "One of keyring_data or keyring_filename must be specified."
            )

        # You can have only one of {keyring_filename, keyring_data}; not
        # both.
        if self.keyring_filename and self.keyring_data:
            raise ValidationError(
                "Only one of keyring_filename or keyring_data can be "
                "specified."
            )

    def clean_fields(self, exclude=None):
        self.priority = self._generate_priority()
        self.skip_keyring_verification = (
            self._generate_skip_keyring_verification()
        )
        super().clean_fields(exclude)

    def _generate_priority(self):
        is_new_entry = False

        if self.pk:
            try:
                BootSource.objects.get(pk=self.pk)
            except BootSource.DoesNotExist:
                is_new_entry = True
        else:
            is_new_entry = True

        if is_new_entry:
            max_priority = (
                BootSource.objects.aggregate(Max("priority"))["priority__max"]
                or 0
            )
            return max_priority + 1

        return self.priority

    def _generate_skip_keyring_verification(self):
        skip = self.skip_keyring_verification
        if self.skip_keyring_verification is None:
            skip = self.url.endswith(".json")
        return skip

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
            with open(self.keyring_filename, "rb") as keyring_file:
                keyring_data = keyring_file.read()
        return {
            "url": self.url,
            "keyring_data": bytes(keyring_data),
            "selections": [],
        }

    def compare_dict_without_selections(self, other):
        """Compare this `BootSource`, as a dict, to another, as a dict.

        Only the keys ``url`` and ``keyring_data`` are relevant.
        """
        keys = "url", "keyring_data"
        this = self.to_dict_without_selections()
        return all(this[key] == other[key] for key in keys)

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
        data["selections"] = [
            selection.to_dict()
            for selection in self.bootsourceselection_set.all()
        ]
        # Always download all bootloaders from the stream. This will allow
        # machines to boot and get a 'Booting under direction of MAAS' message
        # even if boot images for that arch haven't downloaded yet.
        for bootloader in self.bootsourcecache_set.exclude(
            bootloader_type=None
        ):
            data["selections"].append(
                {
                    "os": bootloader.os,
                    "release": bootloader.bootloader_type,
                    "arch": [bootloader.arch],
                }
            )
        # NOTE: release notifications are not a thing anymore in MAAS from 2.9 (IIRC)
        # Leaving this here if we'll ever decide to re-use them.
        # Always download all release notifications from the stream.
        for release_notification in self.bootsourcecache_set.filter(
            release="notifications"
        ):
            data["selections"].append(
                {
                    "os": release_notification.os,
                    "release": release_notification.release,
                    "arch": [release_notification.arch],
                }
            )
        return data

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        related_selections = BootSourceSelection.objects.filter(
            boot_source=self
        )
        for selection in related_selections:
            selection.force_delete()

        return super().delete(*args, **kwargs)
