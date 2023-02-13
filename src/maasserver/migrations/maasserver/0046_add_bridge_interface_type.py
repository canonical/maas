from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0045_add_node_to_filesystem")]

    operations = [
        migrations.CreateModel(
            name="ChildInterface",
            fields=[],
            options={"abstract": False, "proxy": True},
            bases=("maasserver.interface",),
        ),
        migrations.AlterField(
            model_name="interface",
            name="type",
            field=models.CharField(
                choices=[
                    ("physical", "Physical interface"),
                    ("bond", "Bond"),
                    ("bridge", "Bridge"),
                    ("vlan", "VLAN interface"),
                    ("alias", "Alias"),
                    ("unknown", "Unknown"),
                ],
                editable=False,
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="BridgeInterface",
            fields=[],
            options={
                "verbose_name": "Bridge",
                "abstract": False,
                "verbose_name_plural": "Bridges",
                "proxy": True,
            },
            bases=("maasserver.childinterface",),
        ),
    ]
