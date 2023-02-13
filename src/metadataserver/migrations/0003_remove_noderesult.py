from django.db import migrations, models

from metadataserver.enum import RESULT_TYPE, SCRIPT_STATUS


def noderesult_to_scriptresult(apps, schema_editor):
    NodeResult = apps.get_model("metadataserver", "NodeResult")
    ScriptSet = apps.get_model("metadataserver", "ScriptSet")
    ScriptResult = apps.get_model("metadataserver", "ScriptResult")

    for node_result in NodeResult.objects.all():
        node = node_result.node
        if node_result.result_type == RESULT_TYPE.COMMISSIONING:
            if node.current_commissioning_script_set is None:
                script_set = ScriptSet.objects.create(
                    node=node, result_type=RESULT_TYPE.COMMISSIONING
                )
                node.current_commissioning_script_set = script_set
                node.save()
            else:
                script_set = node.current_commissioning_script_set
        elif node_result.result_type == RESULT_TYPE.INSTALLATION:
            if node.current_installation_script_set is None:
                script_set = ScriptSet.objects.create(
                    node=node, result_type=RESULT_TYPE.INSTALLATION
                )
                node.current_installation_script_set = script_set
                node.save()
            else:
                script_set = node.current_installation_script_set
        else:
            # Unknown result_type, this shouldn't happen.
            continue

        # ScriptResults don't store the extention in the name.
        if node_result.name.endswith(".out") or node_result.name.endswith(
            ".err"
        ):
            script_name = node_result.name[0:-4]
        else:
            script_name = node_result.name

        if node_result.script_result == 0:
            status = SCRIPT_STATUS.PASSED
        else:
            status = SCRIPT_STATUS.FAILED

        script_result, _ = ScriptResult.objects.get_or_create(
            created=node_result.created,
            updated=node_result.updated,
            script_set=script_set,
            status=status,
            exit_status=node_result.script_result,
            script_name=script_name,
        )
        if node_result.name.endswith(".err"):
            script_result.stderr = node_result.data
        else:
            script_result.stdout = node_result.data
        script_result.save()


class Migration(migrations.Migration):
    dependencies = [("metadataserver", "0002_script_models")]

    operations = [migrations.RunPython(noderesult_to_scriptresult)]
