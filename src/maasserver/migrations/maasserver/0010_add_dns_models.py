from django.db import migrations, models
import django.db.models.deletion

import maasserver.fields
import maasserver.models.cleansave
import maasserver.models.dnsresource


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0009_remove_routers_field_from_node")]

    operations = [
        migrations.CreateModel(
            name="DNSResource",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        primary_key=True,
                        auto_created=True,
                        serialize=False,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "name",
                    models.CharField(
                        blank=True,
                        null=True,
                        max_length=63,
                        validators=[
                            maasserver.models.dnsresource.validate_dnsresource_name
                        ],
                    ),
                ),
                (
                    "ttl",
                    models.PositiveIntegerField(
                        default=None, null=True, blank=True
                    ),
                ),
            ],
            options={
                "verbose_name": "DNSResource",
                "verbose_name_plural": "DNSResources",
            },
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="Domain",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        primary_key=True,
                        auto_created=True,
                        serialize=False,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "name",
                    maasserver.fields.DomainNameField(
                        unique=True, max_length=256
                    ),
                ),
                (
                    "authoritative",
                    models.NullBooleanField(default=True, db_index=True),
                ),
            ],
            options={
                "verbose_name": "Domain",
                "verbose_name_plural": "Domains",
            },
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.AddField(
            model_name="dnsresource",
            name="domain",
            field=models.ForeignKey(
                default=0,
                null=True,
                to="maasserver.Domain",
                on_delete=django.db.models.deletion.PROTECT,
            ),
        ),
        migrations.AddField(
            model_name="dnsresource",
            name="ip_addresses",
            field=models.ManyToManyField(
                blank=True, to="maasserver.StaticIPAddress"
            ),
        ),
        migrations.AddField(
            model_name="node",
            name="domain",
            field=models.ForeignKey(
                default=None,
                null=True,
                to="maasserver.Domain",
                on_delete=django.db.models.deletion.PROTECT,
            ),
        ),
    ]
