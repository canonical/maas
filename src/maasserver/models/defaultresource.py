from django.db.models import ForeignKey, Manager, PROTECT

from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.models.zone import Zone


class DefaultResourceManager(Manager):
    """Manager for :class:`DefaultResource` model.

    Don't import or instantiate this directly; access as `<Class>.objects` on
    the model class it manages.
    """

    def get_default_zone(self) -> Zone:
        """Return the default zone."""
        return self.first().zone


class DefaultResource(CleanSave, TimestampedModel):
    """Records the default resources."""

    zone = ForeignKey(Zone, on_delete=PROTECT)

    objects = DefaultResourceManager()
