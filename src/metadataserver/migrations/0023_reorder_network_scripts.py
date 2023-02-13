from django.db import migrations


def reorder_network_scripts(apps, schema_editor):
    ScriptResult = apps.get_model("metadataserver", "ScriptResult")
    old_lldp_scripts = ScriptResult.objects.filter(
        script_name="99-maas-02-capture-lldp"
    )
    old_lldp_scripts.update(script_name="99-maas-01-capture-lldp")
    old_ipaddr_scripts = ScriptResult.objects.filter(
        script_name="99-maas-03-network-interfaces"
    )
    old_ipaddr_scripts.update(script_name="40-maas-01-network-interfaces")
    old_sriov_scripts = ScriptResult.objects.filter(
        script_name="99-maas-04-network-interfaces-with-sriov"
    )
    old_sriov_scripts.update(
        script_name="40-maas-02-network-interfaces-with-sriov"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("metadataserver", "0022_internet-connectivity-network-validation")
    ]

    operations = [migrations.RunPython(reorder_network_scripts)]
