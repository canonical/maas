import django.core.validators
from django.db import migrations, models

import maasserver.models.dnspublication


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0057_initial_dns_publication")]

    operations = [
        migrations.AlterField(
            model_name="dnspublication",
            name="serial",
            field=models.BigIntegerField(
                editable=False,
                validators=(
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(4294967295),
                ),
                default=maasserver.models.dnspublication.next_serial,
            ),
        )
    ]
