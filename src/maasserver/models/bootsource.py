# Copyright 2014-2025 Canonical Ltd.  This software is licensed under the
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

from maascommon.workflows.bootresource import (
    FETCH_MANIFEST_AND_UPDATE_CACHE_WORKFLOW_NAME,
    POST_UPDATE_BOOT_SOURCE_URL_WORKFLOW_NAME,
    PostUpdateBootSourceUrlParam,
)
from maasserver.models.bootsourceselection import BootSourceSelection
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.workflow import start_workflow


class ImageManifest(Model):
    boot_source = ForeignKey(
        "maasserver.BootSource",
        on_delete=CASCADE,
    )

    manifest = JSONField()


class BootSource(CleanSave, TimestampedModel):
    """A source for boot resources."""

    name = CharField(
        null=False,
        blank=True,
        unique=True,
        max_length=255,
        help_text="Name of this BootSource.",
    )

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

    enabled = BooleanField(
        null=False,
        blank=True,
        default=True,
        help_text="Whether to download boot images from this source or not.",
    )

    def clean(self, *args, **kwargs):
        super().clean(*args, **kwargs)

        # You have to specify one of {keyring_data, keyring_filename} unless you are using an unsigned stream.
        if (
            not self.skip_keyring_verification
            and not self.keyring_filename
            and not self.keyring_data
        ):
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
        # Always strip the trailing slash
        self.url = self.url.rstrip("/")
        if not self.name:
            self.name = self.url
        if self.priority is None:
            self.priority = self._generate_priority()
        self.skip_keyring_verification = (
            self._generate_skip_keyring_verification()
        )
        if self.enabled is None:
            self.enabled = True
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

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        related_selections = BootSourceSelection.objects.filter(
            boot_source=self
        )
        for selection in related_selections:
            selection.delete()

        return super().delete(*args, **kwargs)

    def verify_selections_after_url_update(self):
        start_workflow(
            workflow_name=POST_UPDATE_BOOT_SOURCE_URL_WORKFLOW_NAME,
            param=PostUpdateBootSourceUrlParam(self.id),
        )

    def refetch_manifest(self):
        start_workflow(
            workflow_name=FETCH_MANIFEST_AND_UPDATE_CACHE_WORKFLOW_NAME,
            param=self.id,
        )
