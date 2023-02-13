from django.db import migrations

source = "Initial publication"


def create_initial_publication(apps, schema_editor):
    # We can't import the DNSPublication model directly as it may be a newer
    # version than this migration expects. We use the historical version.
    DNSPublication = apps.get_model("maasserver", "DNSPublication")
    if not DNSPublication.objects.all().exists():
        publication = DNSPublication(source=source)
        publication.save()


def remove_initial_publication(apps, schema_editor):
    # We can't import the DNSPublication model directly as it may be a newer
    # version than this migration expects. We use the historical version.
    DNSPublication = apps.get_model("maasserver", "DNSPublication")
    for publication in DNSPublication.objects.order_by("id")[:1]:
        if publication.source == source:
            publication.delete()


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0056_zone_serial_ownership")]

    operations = [
        migrations.RunPython(
            create_initial_publication, remove_initial_publication
        )
    ]
