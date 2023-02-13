from django.db import migrations, models
import django.db.models.deletion

import maasserver.models.dnsresource
import maasserver.models.node


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0022_extract_ip_for_bmcs")]

    operations = [
        migrations.AddField(
            model_name="dnsdata",
            name="ttl",
            field=models.PositiveIntegerField(
                null=True, default=None, blank=True
            ),
        ),
        migrations.AddField(
            model_name="domain",
            name="ttl",
            field=models.PositiveIntegerField(
                null=True, default=None, blank=True
            ),
        ),
        migrations.AddField(
            model_name="node",
            name="address_ttl",
            field=models.PositiveIntegerField(
                null=True, default=None, blank=True
            ),
        ),
        # No data has ever lived here, so this is really just a rename.
        migrations.RemoveField(model_name="dnsresource", name="ttl"),
        migrations.AddField(
            model_name="dnsresource",
            name="address_ttl",
            field=models.PositiveIntegerField(
                null=True, default=None, blank=True
            ),
        ),
        migrations.AlterField(
            model_name="dnsresource",
            name="domain",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to="maasserver.Domain",
            ),
        ),
        migrations.AlterField(
            model_name="node",
            name="domain",
            field=models.ForeignKey(
                null=False,
                to="maasserver.Domain",
                on_delete=django.db.models.deletion.PROTECT,
            ),
        ),
    ]
