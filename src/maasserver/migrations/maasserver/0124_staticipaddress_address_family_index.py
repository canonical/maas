from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("maasserver", "0123_make_iprange_comment_default_to_empty_string")
    ]

    operations = [
        migrations.RunSQL(
            "CREATE INDEX maasserver_staticipaddress__ip_family ON maasserver_staticipaddress (family(ip))",
            "DROP INDEX maasserver_staticipaddress__ip_family",
        )
    ]
