from django.db import migrations
from django.utils import timezone

from maasserver.models.resourcepool import (
    DEFAULT_RESOURCEPOOL_DESCRIPTION,
    DEFAULT_RESOURCEPOOL_NAME,
)


def forwards(apps, schema_editor):
    ResourcePool = apps.get_model("maasserver", "ResourcePool")
    now = timezone.now()
    ResourcePool.objects.get_or_create(
        id=0,
        defaults={
            "name": DEFAULT_RESOURCEPOOL_NAME,
            "description": DEFAULT_RESOURCEPOOL_DESCRIPTION,
            "created": now,
            "updated": now,
        },
    )


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0133_add_resourcepool_model")]

    operations = [migrations.RunPython(forwards)]
