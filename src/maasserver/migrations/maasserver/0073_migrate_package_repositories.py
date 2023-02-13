from django.db import migrations

from maasserver.models import timestampedmodel


# Copied from Node model.
def move_package_repositories(apps, schema_editor):
    Config = apps.get_model("maasserver", "Config")
    PackageRepository = apps.get_model("maasserver", "PackageRepository")

    # Copied from PackageRepository model.
    MAIN_ARCHES = ["amd64", "i386"]
    PORTS_ARCHES = ["armhf", "arm64", "powerpc", "ppc64el"]

    now = timestampedmodel.now()

    for config in Config.objects.filter(name="main_archive"):
        PackageRepository.objects.create(
            name=config.name,
            description=config.name,
            url=config.value,
            arches=MAIN_ARCHES,
            default=True,
            enabled=True,
            created=now,
            updated=now,
        )
        config.delete()

    if not PackageRepository.objects.filter(name="main_archive").exists():
        PackageRepository.objects.create(
            name="main_archive",
            description="main_archive",
            url="http://archive.ubuntu.com/ubuntu",
            arches=MAIN_ARCHES,
            default=True,
            enabled=True,
            created=now,
            updated=now,
        )

    for config in Config.objects.filter(name="ports_archive"):
        PackageRepository.objects.create(
            name=config.name,
            description=config.name,
            url=config.value,
            arches=PORTS_ARCHES,
            default=True,
            enabled=True,
            created=now,
            updated=now,
        )
        config.delete()

    if not PackageRepository.objects.filter(name="ports_archive").exists():
        PackageRepository.objects.create(
            name="ports_archive",
            description="ports_archive",
            url="http://ports.ubuntu.com/ubuntu-ports",
            arches=PORTS_ARCHES,
            default=True,
            enabled=True,
            created=now,
            updated=now,
        )


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0072_packagerepository")]

    operations = [migrations.RunPython(move_package_repositories)]
