from django.db import migrations


def migrate_spaces_from_subnet_to_vlan(apps, schema_editor):
    Space = apps.get_model("maasserver", "Space")
    if Space.objects.count() <= 1:
        # If the default space is the only space on the system, (and it has
        # not been renamed), that means the MAAS admin wasn't using spaces. So
        # migrate them all to the NULL space. (no action required)
        spaces = list(Space.objects.all())
        if len(spaces) == 1:
            default_space = spaces[0]
            name = default_space.name
            if name is None or name == "" or name == "space-0":
                # One space, default name. Skip migration to VLANs.
                return
            else:
                # One space, but the name has been customized. Keep it.
                pass
        else:
            # Default space was never created.
            return
    VLAN = apps.get_model("maasserver", "VLAN")
    for vlan in VLAN.objects.all().prefetch_related("subnet_set__space"):
        space = None
        for subnet in vlan.subnet_set.all():
            if space is None:
                space = subnet.space
            elif subnet.space_id > space.id:
                # Select the most recently created space if there are multiple.
                space = subnet.space
        vlan.space = space
        vlan.save()


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0099_set_default_vlan_field")]

    operations = [migrations.RunPython(migrate_spaces_from_subnet_to_vlan)]
