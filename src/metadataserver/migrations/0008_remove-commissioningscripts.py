from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("metadataserver", "0007_migrate-commissioningscripts")]

    operations = [migrations.DeleteModel(name="CommissioningScript")]
