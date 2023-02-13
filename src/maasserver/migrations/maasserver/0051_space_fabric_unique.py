from random import randint
import re

from django.db import migrations, models

import maasserver.models.fabric
import maasserver.models.space


def fix_model(apps, schema_editor, model_name, prefix):
    cls = apps.get_model("maasserver", model_name)
    # Pass 1: assign values to all of the null/empty names, and identify the
    # duplicates.
    duplicates = set()
    for instance in cls.objects.all():
        if instance.name is None or instance.name == "":
            instance.name = "%s-%d" % (prefix, instance.id)
            instance.save()
        elif cls.objects.filter(name=instance.name).count() > 1:
            # We know that anything we would be renaming None to is reserved to
            # only our instance.  That means that we don't have to do all the
            # renmaes before we check for duplicates.
            duplicates.add(instance)
    # Pass 2: Rename anything that was a duplicate.  Because blanks are now
    # illegal in the name (and should always have been) any instance that we
    # need to rename to fix duplication will need to have blanks replaced with
    # hypens.
    # No preference is given to any instance: all duplicates will get a new
    # name.
    for instance in duplicates:
        # Get rid of the instance, if any.
        instance.name = re.sub(" ", "-", instance.name)
        # First, try ${NAME}-${ID}, then go with ${NAME}-${ID}-${RANDOM}
        name = "%s-%d" % (instance.name, instance.id)
        if cls.objects.filter(name=name).exists():
            retries = 20
            while retries > 0 and cls.objects.filter(name=name).exists():
                name = "%s-%d-%d" % (
                    instance.name,
                    instance.id,
                    randint(1, 100000),
                )
                retries -= 1
            # We tried, and we give up.  Just change it to the default name.
            # Note that to get here, we tried ${NAME}-${ID} and 20 other
            # randomly related names and they _ALL_ had existing collisions in
            # the data base.
            if retries == 0:
                name = "%s-%d" % (prefix, instance.id)
        instance.name = name
        instance.save()


def fix_space_names(apps, schema_editor):
    fix_model(apps, schema_editor, "Space", "space")


def fix_fabric_names(apps, schema_editor):
    fix_model(apps, schema_editor, "Fabric", "fabric")


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0050_modify_external_dhcp_on_vlan")]

    operations = [
        migrations.RunPython(fix_space_names),
        migrations.RunPython(fix_fabric_names),
        migrations.AlterField(
            model_name="space",
            name="name",
            field=models.CharField(
                null=True,
                blank=True,
                unique=True,
                validators=[maasserver.models.space.validate_space_name],
                max_length=256,
            ),
        ),
        migrations.AlterField(
            model_name="fabric",
            name="name",
            field=models.CharField(
                null=True,
                blank=True,
                unique=True,
                validators=[maasserver.models.fabric.validate_fabric_name],
                max_length=256,
            ),
        ),
    ]
