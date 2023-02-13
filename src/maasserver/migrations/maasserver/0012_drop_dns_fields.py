from django.db import migrations, models
import django.db.models.deletion

import maasserver.fields
import maasserver.models.cleansave
import maasserver.models.dnsresource


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0011_domain_data")]

    operations = [
        migrations.RemoveField(model_name="staticipaddress", name="hostname"),
        migrations.AlterField(
            model_name="dnsresource",
            name="domain",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                default=0,
                to="maasserver.Domain",
            ),
        ),
        migrations.AlterField(
            model_name="node",
            name="domain",
            field=models.ForeignKey(
                default=0,
                null=False,
                to="maasserver.Domain",
                on_delete=django.db.models.deletion.PROTECT,
            ),
        ),
    ]
