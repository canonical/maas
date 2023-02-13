from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0118_add_iscsi_storage_pod")]

    # convert this to a no-op as it was previously updating the Subnet.vlan
    # default to get_default_vlan, which failed as it was importing code from
    # models. The default has now been dropped, since otherwise Django keeps
    # adding a migration to set it, even if there's actually nothing to do (the
    # field was already NOT NULL, so default doesn't do anything in the patch)
    operations = [migrations.RunPython(migrations.RunPython.noop)]
