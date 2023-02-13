from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0001_initial")]

    operations = [migrations.DeleteModel(name="CandidateName")]
