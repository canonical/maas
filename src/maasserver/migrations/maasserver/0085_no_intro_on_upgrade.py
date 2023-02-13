from django.db import migrations


def no_intro_on_upgrade(apps, schema_editor):
    Config = apps.get_model("maasserver", "Config")
    UserProfile = apps.get_model("maasserver", "UserProfile")
    if UserProfile.objects.exists():
        # Users already exist so this is an upgrade and no need to for
        # the intro to be completed. This is done with UserProfile because
        # only users that can login into MAAS get a profile.
        obj, created = Config.objects.get_or_create(
            name="completed_intro", defaults={"value": True}
        )
        if not created:
            obj.value = True
            obj.save()


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0084_add_default_user_to_node_model")]

    operations = [migrations.RunPython(no_intro_on_upgrade)]
