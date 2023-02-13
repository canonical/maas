from django.db import migrations, models

import maasserver.models.cleansave
import maasserver.models.dnsdata


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0017_remove_node_power_type")]

    operations = [
        migrations.CreateModel(
            name="DNSData",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        primary_key=True,
                        auto_created=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "rrtype",
                    models.CharField(
                        validators=[maasserver.models.dnsdata.validate_rrtype],
                        max_length=8,
                        help_text="Resource record type",
                    ),
                ),
                (
                    "rrdata",
                    models.TextField(
                        help_text="Entire right-hand side of the resource record."
                    ),
                ),
            ],
            options={
                "verbose_name": "DNSData",
                "verbose_name_plural": "DNSData",
            },
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.AlterField(
            model_name="dnsresource",
            name="name",
            field=models.CharField(max_length=191, blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="dnsresource",
            name="ttl",
            field=models.PositiveIntegerField(
                default=None, null=True, blank=True
            ),
        ),
        migrations.AddField(
            model_name="dnsdata",
            name="dnsresource",
            field=models.ForeignKey(
                to="maasserver.DNSResource",
                help_text="DNSResource which is the left-hand side.",
                on_delete=models.CASCADE,
            ),
        ),
    ]
