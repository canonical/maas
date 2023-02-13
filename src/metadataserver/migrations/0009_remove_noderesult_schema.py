from django.db import migrations, models, utils


class DeleteModel(migrations.DeleteModel):
    """
    Delete model operation that handles the case where it might already
    be deleted. This is needed because of lp:1669570 where the schema migration
    was previously in 0002_script_models. We need to handle the case where
    users have upgraded and others failed to upgrade.
    """

    def database_forwards(
        self, app_label, schema_editor, from_state, to_state
    ):
        try:
            super().database_forwards(
                app_label, schema_editor, from_state, to_state
            )
        except utils.ProgrammingError:
            # Error is raised when the table has already been deleted. This
            # is for users that upgrade to 2.2 beta1 before 2.2 beta3.
            pass


class Migration(migrations.Migration):
    dependencies = [("metadataserver", "0008_remove-commissioningscripts")]

    operations = [DeleteModel(name="NodeResult")]
