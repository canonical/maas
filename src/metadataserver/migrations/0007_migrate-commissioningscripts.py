from django.db import migrations, models
from django.utils import timezone

from metadataserver.enum import SCRIPT_TYPE


def commissioningscript_to_script(apps, schema_editor):
    CommissioningScript = apps.get_model(
        "metadataserver", "CommissioningScript"
    )
    Script = apps.get_model("metadataserver", "Script")
    VersionedTextFile = apps.get_model("maasserver", "VersionedTextFile")

    now = timezone.now()
    for commissioning_script in CommissioningScript.objects.all():
        vtf = VersionedTextFile.objects.create(
            created=now,
            updated=now,
            data=commissioning_script.content.decode(),
        )
        Script.objects.create(
            created=now,
            updated=now,
            name=commissioning_script.name,
            script=vtf,
            script_type=SCRIPT_TYPE.COMMISSIONING,
        )


class Migration(migrations.Migration):
    dependencies = [("metadataserver", "0006_scriptresult_combined_output")]

    operations = [migrations.RunPython(commissioningscript_to_script)]
