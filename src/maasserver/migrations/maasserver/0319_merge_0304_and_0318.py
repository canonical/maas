from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("maasserver", "0317_migrate_defaultresource_zone"),
        ("maasserver", "0318_add_port_to_forward_dns_servers"),
    ]

    operations = []
