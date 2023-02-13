from django.db import migrations, models

# IPs must be unique across the entire table, except DISCOVERED addresses
# (which are type 6). The unique_together ensures that IP addresses are also
# unique amongst their own alloc_type. This index strengthens that.
staticipaddress_unique_index_create = (
    "CREATE UNIQUE INDEX maasserver_staticipaddress__discovered_unique"
    "    ON maasserver_staticipaddress (ip)"
    "    WHERE alloc_type != 6"
)


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0120_bootsourcecache_extra")]

    operations = [
        migrations.AlterField(
            model_name="staticipaddress",
            name="ip",
            field=models.GenericIPAddressField(
                editable=False,
                verbose_name="IP",
                blank=True,
                null=True,
                default=None,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="staticipaddress", unique_together={("alloc_type", "ip")}
        ),
        migrations.RunSQL(staticipaddress_unique_index_create),
    ]
