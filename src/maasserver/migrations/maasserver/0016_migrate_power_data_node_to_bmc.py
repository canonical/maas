from django.db import migrations

from maasserver.models import timestampedmodel
from provisioningserver.drivers import SETTING_SCOPE
from provisioningserver.drivers.power.registry import PowerDriverRegistry


# Copied from BMC model.
def scope_power_parameters(power_type, power_params):
    """Separate the global, bmc related power_parameters from the local,
    node-specific ones."""
    if not power_type:
        # If there is no power type, treat all params as node params.
        return ({}, power_params)
    power_driver = PowerDriverRegistry.get_item(power_type)
    if power_driver is None:
        # If there is no power driver, treat all params as node params.
        return ({}, power_params)
    power_fields = power_driver.settings
    if not power_fields:
        # If there is no parameter info, treat all params as node params.
        return ({}, power_params)
    bmc_params = {}
    node_params = {}
    for param_name in power_params:
        power_field = power_driver.get_setting(param_name)
        if power_field and power_field.get("scope") == SETTING_SCOPE.BMC:
            bmc_params[param_name] = power_params[param_name]
        else:
            node_params[param_name] = power_params[param_name]
    return (bmc_params, node_params)


# Copied from Node model.
def clean_orphaned_bmcs(Node, BMC):
    # If bmc has changed post-save, clean up any newly orphaned BMC's.
    used_bmcs = Node.objects.values_list("bmc_id", flat=True).distinct()
    BMC.objects.exclude(id__in=used_bmcs).delete()


# Copied from Node model.
def update_power_type_and_parameters(BMC, node, now):
    power_type = node.power_type
    power_params = node.instance_power_parameters
    bmc_params, node_params = scope_power_parameters(power_type, power_params)
    node.instance_power_parameters = node_params
    (bmc, _) = BMC.objects.get_or_create(
        power_type=power_type,
        power_parameters=bmc_params,
        created=now,
        updated=now,
    )
    node.bmc = bmc


def migrate_power_data_from_node_to_bmc(apps, schema_editor):
    now = timestampedmodel.now()
    Node = apps.get_model("maasserver", "Node")
    BMC = apps.get_model("maasserver", "BMC")
    for node in Node.objects.all().order_by("id"):
        # update bmc info in new BMC tables as if we're re-saving the form
        update_power_type_and_parameters(BMC, node, now)
        node.save()
    clean_orphaned_bmcs(Node, BMC)


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0015_add_bmc_model")]

    operations = [migrations.RunPython(migrate_power_data_from_node_to_bmc)]
