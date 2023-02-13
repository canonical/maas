from django.db import migrations, models

from maasserver.enum import NODE_TYPE


def convert_installable_to_node_type(apps, schema_editor):
    Node = apps.get_model("maasserver", "Node")
    for node in Node.objects.all():
        node.routers = ""
        if node.installable:
            node.node_type = NODE_TYPE.MACHINE
        else:
            node.node_type = NODE_TYPE.DEVICE
        node.save(update_fields=["node_type"])


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0003_add_node_type_to_node")]

    operations = [migrations.RunPython(convert_installable_to_node_type)]
