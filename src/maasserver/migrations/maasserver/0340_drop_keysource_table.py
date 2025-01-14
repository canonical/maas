# Generated by Django 4.2.11 on 2025-01-07 13:02

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("maasserver", "0339_migrate_keysource_table"),
    ]

    operations = [
        # Remove the ForeignKey from SSHKey to KeySource
        migrations.RemoveField(
            model_name="sshkey",
            name="keysource",
        ),
        # Delete KeySource model
        migrations.DeleteModel(
            name="KeySource",
        ),
    ]