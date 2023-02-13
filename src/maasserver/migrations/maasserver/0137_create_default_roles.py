from django.conf import settings
from django.db import migrations


def forwards(apps, schema_editor):
    ResourcePool = apps.get_model("maasserver", "ResourcePool")
    Role = apps.get_model("maasserver", "Role")
    User = apps.get_model(settings.AUTH_USER_MODEL)

    for pool in ResourcePool.objects.all():
        # create a role for each pool
        role = Role(
            name=f"role-{pool.name}",
            description=f"Default role for resource pool {pool.name}",
        )
        role.save()
        role.resource_pools.add(pool)
        if pool.id == 0:
            # assign existing users (except system ones) to the default pool.
            users = User.objects.exclude(
                username__in=("MAAS", "maas-init-node")
            )
            role.users.add(*users)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("maasserver", "0136_add_user_role_models"),
    ]

    operations = [migrations.RunPython(forwards)]
