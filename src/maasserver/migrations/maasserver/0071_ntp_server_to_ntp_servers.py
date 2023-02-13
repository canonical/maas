from django.db import migrations

sql_ntp_server_to_ntp_servers = """\
UPDATE maasserver_config
   SET name = 'ntp_servers'
 WHERE name = 'ntp_server'
"""

sql_ntp_servers_to_ntp_server = """\
UPDATE maasserver_config
   SET name = 'ntp_server'
 WHERE name = 'ntp_servers'
"""


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0070_allow_null_vlan_on_interface")]

    operations = [
        migrations.RunSQL(
            sql_ntp_server_to_ntp_servers, sql_ntp_servers_to_ntp_server
        )
    ]
