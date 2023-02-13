from django.contrib.postgres.fields import JSONField
from django.db import migrations, models
from django.db.models.expressions import CombinedExpression, F, Value


def lxd_bmcs_add_project(apps, schema_editor):
    BMC = apps.get_model("maasserver", "BMC")
    BMC.objects.filter(power_type="lxd").update(
        power_parameters=CombinedExpression(
            F("power_parameters"),
            "||",
            Value({"project": "default"}, JSONField()),
        )
    )


class Migration(migrations.Migration):
    dependencies = [
        ("maasserver", "0220_nodedevice"),
    ]

    operations = [
        migrations.AddField(
            model_name="virtualmachine",
            name="project",
            field=models.TextField(default="default"),
            preserve_default=False,
        ),
        migrations.AlterUniqueTogether(
            name="virtualmachine",
            unique_together={("bmc", "identifier", "project")},
        ),
        migrations.RunPython(lxd_bmcs_add_project),
    ]
