from datetime import datetime

from django.db import migrations


def migrate_default_zone(apps, schema_editor):
    Zone = apps.get_model("maasserver", "Zone")
    DefaultResource = apps.get_model("maasserver", "DefaultResource")
    default_zone_qs = Zone.objects.filter(name="default")

    now = datetime.now()
    if default_zone_qs.exists():
        DefaultResource.objects.create(
            zone=default_zone_qs.first(), created=now, updated=now
        )
    # If the "default" zone does not exist but there are other zones, it means it was renamed. We have to pick one.
    elif Zone.objects.exists():
        DefaultResource.objects.create(
            zone=Zone.objects.first(), created=now, updated=now
        )
    else:
        zone = Zone.objects.create(name="default", created=now, updated=now)
        DefaultResource.objects.create(created=now, updated=now, zone=zone)


class Migration(migrations.Migration):
    dependencies = [
        ("maasserver", "0316_add_defaultresource_table"),
    ]

    operations = [migrations.RunPython(migrate_default_zone)]
