from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

import maasserver.utils.dns


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("maasserver", "0130_node_locked_flag"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="node_hostname",
            field=models.CharField(
                validators=[maasserver.utils.dns.validate_hostname],
                default="",
                blank=True,
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.SET_NULL,
                to=settings.AUTH_USER_MODEL,
                default=None,
                null=True,
                blank=True,
                editable=False,
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="username",
            field=models.CharField(default="", blank=True, max_length=32),
        ),
        migrations.AlterField(
            model_name="event",
            name="node",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.SET_NULL,
                to="maasserver.Node",
                null=True,
                editable=False,
            ),
        ),
        migrations.AlterField(
            model_name="event",
            name="type",
            field=models.ForeignKey(
                to="maasserver.EventType",
                editable=False,
                on_delete=django.db.models.deletion.PROTECT,
            ),
        ),
    ]
