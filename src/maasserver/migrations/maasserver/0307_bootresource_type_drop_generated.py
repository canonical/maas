# Generated by Django 3.2.12 on 2023-08-31 08:15

from django.db import migrations, models


def update_generated_rtype(apps, schema_editor):
    # change GENERATED rtype to UPLOADED
    BootResource = apps.get_model("maasserver", "BootResource")
    BootResource.objects.filter(rtype=1).update(rtype=2)


class Migration(migrations.Migration):
    dependencies = [
        ("maasserver", "0306_diskless_ephemeral_deploy"),
    ]

    operations = [
        migrations.RunPython(update_generated_rtype),
        migrations.AlterField(
            model_name="bootresource",
            name="rtype",
            field=models.IntegerField(
                choices=[(0, "Synced"), (2, "Uploaded")], editable=False
            ),
        ),
    ]