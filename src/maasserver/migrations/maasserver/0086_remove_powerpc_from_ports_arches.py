from django.db import migrations


def remove_powerpc_from_ports_arches(apps, schema_editor):
    PORTS_ARCHES = ["armhf", "arm64", "ppc64el"]
    PackageRepository = apps.get_model("maasserver", "PackageRepository")
    ports_archive = PackageRepository.objects.filter(
        name="ports_archive", default=True
    ).first()
    if ports_archive is not None:
        ports_archive.arches = PORTS_ARCHES
        ports_archive.save()


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0085_no_intro_on_upgrade")]

    operations = [migrations.RunPython(remove_powerpc_from_ports_arches)]
