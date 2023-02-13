from django.db import migrations, models
import django.db.models.deletion


def set_machines_default_resource_pool(apps, schema_editor):
    """Assign all machines to the default resource pool."""
    ResourcePool = apps.get_model("maasserver", "ResourcePool")
    Machine = apps.get_model("maasserver", "Machine")
    pool = ResourcePool.objects.get(id=0)
    Machine.objects.all().update(pool=pool)


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0134_create_default_resourcepool")]

    operations = [
        migrations.AddField(
            model_name="node",
            name="pool",
            field=models.ForeignKey(
                to="maasserver.ResourcePool",
                on_delete=django.db.models.deletion.PROTECT,
                default=None,
                null=True,
                blank=True,
            ),
        ),
        migrations.RunPython(set_machines_default_resource_pool),
    ]
