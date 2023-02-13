import django
from django.db import migrations, models

import maasserver.fields
import maasserver.models.cleansave


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0082_add_kflavor")]

    operations = [
        migrations.CreateModel(
            name="Discovery",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "discovery_id",
                    models.CharField(
                        null=True, max_length=256, editable=False, unique=True
                    ),
                ),
                (
                    "ip",
                    models.GenericIPAddressField(
                        verbose_name="IP",
                        editable=False,
                        blank=True,
                        null=True,
                        default=None,
                    ),
                ),
                (
                    "mac_address",
                    maasserver.fields.MACAddressField(
                        blank=True, null=True, editable=False
                    ),
                ),
                ("first_seen", models.DateTimeField(editable=False)),
                ("last_seen", models.DateTimeField(editable=False)),
                (
                    "hostname",
                    models.CharField(
                        max_length=256, editable=False, null=True
                    ),
                ),
                (
                    "observer_system_id",
                    models.CharField(max_length=41, editable=False),
                ),
                (
                    "observer_hostname",
                    maasserver.fields.DomainNameField(
                        max_length=256, editable=False, null=True
                    ),
                ),
                (
                    "observer_interface_name",
                    models.CharField(max_length=255, editable=False),
                ),
                (
                    "fabric_name",
                    models.CharField(
                        blank=True, max_length=256, editable=False, null=True
                    ),
                ),
                ("vid", models.IntegerField(blank=True, null=True)),
                (
                    "subnet_cidr",
                    maasserver.fields.CIDRField(
                        blank=True, null=True, editable=False
                    ),
                ),
                (
                    "fabric",
                    models.ForeignKey(
                        editable=False,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        to="maasserver.Fabric",
                    ),
                ),
                (
                    "mdns",
                    models.ForeignKey(
                        editable=False,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        blank=True,
                        null=True,
                        to="maasserver.MDNS",
                    ),
                ),
                (
                    "neighbour",
                    models.ForeignKey(
                        editable=False,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        to="maasserver.Neighbour",
                    ),
                ),
                (
                    "observer",
                    models.ForeignKey(
                        editable=False,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        to="maasserver.Node",
                    ),
                ),
                (
                    "observer_interface",
                    models.ForeignKey(
                        editable=False,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        to="maasserver.Interface",
                    ),
                ),
                (
                    "subnet",
                    models.ForeignKey(
                        editable=False,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        blank=True,
                        null=True,
                        to="maasserver.Subnet",
                    ),
                ),
                (
                    "vlan",
                    models.ForeignKey(
                        editable=False,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        to="maasserver.VLAN",
                    ),
                ),
            ],
            options={
                "managed": False,
                "verbose_name": "Discovery",
                "verbose_name_plural": "Discoveries",
            },
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        )
    ]
