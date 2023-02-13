from django.db import migrations, models


def fix_spelling(apps, schema_editor):
    Service = apps.get_model("maasserver", "Service")
    for service in Service.objects.filter(status="degraged"):
        service.status = "degraded"
        service.save(update_fields=["status"])


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0046_add_bridge_interface_type")]

    operations = [
        migrations.AlterField(
            model_name="service",
            name="status",
            field=models.CharField(
                editable=False,
                default="unknown",
                choices=[
                    ("unknown", "Unknown"),
                    ("running", "Running"),
                    ("degraded", "Degraded"),
                    ("dead", "Dead"),
                    ("off", "Off"),
                ],
                max_length=10,
            ),
        ),
        migrations.RunPython(fix_spelling),
    ]
