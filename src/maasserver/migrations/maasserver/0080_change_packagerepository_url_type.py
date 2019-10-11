# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import maasserver.fields


class Migration(migrations.Migration):

    dependencies = [("maasserver", "0079_add_keysource_model")]

    operations = [
        migrations.AlterField(
            model_name="packagerepository",
            name="url",
            field=maasserver.fields.URLOrPPAField(
                help_text="The URL of the PackageRepository."
            ),
        )
    ]
