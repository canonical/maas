# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Template objects."""

import sys

from django.db.models import CASCADE, CharField, ForeignKey, Manager

from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import get_one


class TemplateManager(Manager):
    def get_by_filename(self, filename):
        return get_one(Template.objects.filter(filename=filename))

    def create_or_update_default(
        self, filename, data, verbosity=0, stdout=sys.stdout
    ):
        """Updates the template indexed with the specified filename with
        the specified data. Creates the template file if it does not exist yet.
        Optionally writes status to stdout (if verbosity > 0).
        """
        # Circular imports
        from maasserver.models import VersionedTextFile

        template = get_one(Template.objects.filter(filename=filename))
        if template is None:
            comment = "Imported default: %s" % filename
            version = VersionedTextFile(data=data, comment=comment)
            version.save()
            template = Template(filename=filename, default_version=version)
            template.save()
            if verbosity > 0:
                stdout.write(comment + "\n")
        else:
            comment = "Updated default: %s" % filename
            version = template.default_version.update(data, comment=comment)
            if version.id != template.default_version_id:
                template.default_version = version
                template.save()
                if verbosity > 0:
                    stdout.write(comment + "\n")
            else:
                if verbosity > 0:
                    stdout.write("Skipped: %s\n" % filename)


class Template(CleanSave, TimestampedModel):
    """A generic `Template` object, with a link to a default version and an
    optional custom version.

    :ivar filename: The filename of this template (/etc/mass/templates/X)
    :ivar default_version: The default value for this template. Useful if the
        template needs to be reset after an accidental edit. MAAS is
        responsible for the default_version; the user is not allowed to set it.
    :ivar version: The current in-use version of this template. If this exists,
        the specified template will be used (rather than the default). If
        not specified, the default_version will be used.
    """

    class Meta:
        verbose_name = "Template"
        verbose_name_plural = "Templates"

    objects = TemplateManager()

    filename = CharField(
        editable=True,
        max_length=64,
        blank=False,
        null=False,
        unique=True,
        help_text="Template filename",
    )

    default_version = ForeignKey(
        "VersionedTextFile",
        on_delete=CASCADE,
        editable=False,
        blank=False,
        null=False,
        related_name="default_templates",
        help_text="Default data for this template.",
    )

    version = ForeignKey(
        "VersionedTextFile",
        on_delete=CASCADE,
        editable=True,
        blank=True,
        null=True,
        related_name="templates",
        help_text="Custom data for this template.",
    )

    @property
    def value(self):
        if self.version is not None:
            return self.version.data
        else:
            return self.default_version.data

    @property
    def default_value(self):
        return self.default_version.data

    @property
    def is_default(self):
        return self.version is None

    def revert(self, verbosity=0, stdout=sys.stdout):
        self.version = None
        self.save()
        if verbosity > 0:
            stdout.write("Reverted template to default: %s\n" % self.filename)

    def update(self, new_text, comment=None):
        if self.version is None:
            version = self.default_version
        else:
            version = self.version
        self.version = version.update(new_text, comment)

    def delete(self, *args, **kwargs):
        if self.default_version is not None:
            # By deleting the oldest version, the deletion should cascade
            # to all other versions of the file.
            self.default_version.get_oldest_version().delete(*args, **kwargs)
        return super().delete(*args, **kwargs)
