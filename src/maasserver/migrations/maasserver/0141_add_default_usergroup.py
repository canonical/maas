from django.conf import settings
from django.db import migrations
from django.utils import timezone

from maasserver.worker_user import user_name as worker_username
from metadataserver.nodeinituser import user_name as node_init_username

DEFAULT_USERGROUP_NAME = "default"
DEFAULT_USERGROUP_DESCRIPTION = "Default user group"


def forwards(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL)
    UserGroup = apps.get_model("maasserver", "UserGroup")
    UserGroupMembership = apps.get_model("maasserver", "UserGroupMembership")
    now = timezone.now()
    default_group, _ = UserGroup.objects.get_or_create(
        id=0,
        defaults={
            "name": DEFAULT_USERGROUP_NAME,
            "description": DEFAULT_USERGROUP_DESCRIPTION,
            "created": now,
            "updated": now,
        },
    )
    special_users = (worker_username, node_init_username)
    for user in User.objects.exclude(username__in=special_users):
        UserGroupMembership.objects.create(user=user, group=default_group)


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0140_add_usergroup_model")]

    operations = [migrations.RunPython(forwards)]
