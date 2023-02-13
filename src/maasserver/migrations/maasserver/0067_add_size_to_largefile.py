import os

from django.db import migrations, models


def get_size_of_content(large_file):
    with large_file.content.open("rb") as stream:
        stream.seek(0, os.SEEK_END)
        return stream.tell()


def set_size_on_all_largefiles(apps, schema_editor):
    LargeFile = apps.get_model("maasserver", "LargeFile")
    for large_file in LargeFile.objects.all():
        large_file.size = get_size_of_content(large_file)
        large_file.save()


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0066_allow_squashfs")]

    operations = [
        migrations.AddField(
            model_name="largefile",
            name="size",
            field=models.BigIntegerField(default=0, editable=False),
        ),
        migrations.RunPython(set_size_on_all_largefiles),
    ]
