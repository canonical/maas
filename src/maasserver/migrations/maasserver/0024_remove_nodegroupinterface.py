from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0023_add_ttl_field")]

    operations = [
        migrations.RemoveField(
            model_name="downloadprogress", name="nodegroup"
        ),
        migrations.RemoveField(model_name="nodegroup", name="api_token"),
        migrations.AlterUniqueTogether(
            name="nodegroupinterface", unique_together=set()
        ),
        migrations.RemoveField(
            model_name="nodegroupinterface", name="nodegroup"
        ),
        migrations.RemoveField(model_name="nodegroupinterface", name="subnet"),
        migrations.RemoveField(model_name="nodegroupinterface", name="vlan"),
        migrations.RemoveField(model_name="node", name="nodegroup"),
        migrations.AddField(
            model_name="node",
            name="status_expires",
            field=models.DateTimeField(
                editable=False, default=None, null=True
            ),
        ),
        migrations.AddField(
            model_name="node",
            name="power_state_queried",
            field=models.DateTimeField(
                editable=False, null=True, default=None
            ),
        ),
        migrations.AddField(
            model_name="node",
            name="url",
            field=models.CharField(
                editable=False, blank=True, max_length=255, default=""
            ),
        ),
        migrations.AddField(
            model_name="vlan",
            name="dhcp_on",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="vlan",
            name="primary_rack",
            field=models.ForeignKey(
                to="maasserver.Node",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="vlan",
            name="secondary_rack",
            field=models.ForeignKey(
                to="maasserver.Node",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                blank=True,
                null=True,
            ),
        ),
        migrations.DeleteModel(name="DownloadProgress"),
        migrations.DeleteModel(name="NodeGroup"),
        migrations.DeleteModel(name="NodeGroupInterface"),
    ]
