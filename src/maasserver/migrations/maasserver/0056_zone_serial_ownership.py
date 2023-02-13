from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0055_dns_publications")]

    operations = [
        # Associate maasserver_zone_serial_seq with maasserver_dnspublication.
        migrations.RunSQL(
            # Forwards.
            (
                "ALTER SEQUENCE maasserver_zone_serial_seq "
                "OWNED BY maasserver_dnspublication.serial"
            ),
            # Reverse.
            ("ALTER SEQUENCE maasserver_zone_serial_seq OWNED BY NONE"),
        ),
        # Ensure that maasserver_zone_serial_seq cycles. It does not seem
        # likely that anyone will exhaust all 2^32 zone serials, but if they
        # do we should behave as the DNS server will expect, i.e. cycle.
        migrations.RunSQL(
            # Forwards.
            "ALTER SEQUENCE maasserver_zone_serial_seq CYCLE",
            # Reverse.
            "ALTER SEQUENCE maasserver_zone_serial_seq NO CYCLE",
        ),
    ]
