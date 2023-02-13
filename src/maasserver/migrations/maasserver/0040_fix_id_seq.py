from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("maasserver", "0039_create_template_and_versionedtextfile_models")
    ]

    operations = [
        migrations.RunSQL(
            """\
            SELECT pg_catalog.setval(
                'maasserver_vlan_id_seq', 
                GREATEST(
                    5001, (SELECT MAX(id)+1 from maasserver_vlan)), false);
            """
        )
    ]
