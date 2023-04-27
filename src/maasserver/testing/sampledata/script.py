from maasserver.enum import NODE_STATUS
from maasserver.models import ScriptSet
from provisioningserver.refresh.node_info_scripts import (
    COMMISSIONING_OUTPUT_NAME,
)


def make_scripts(machine, lxd_info: bytes):
    commissioning_set = ScriptSet.objects.create_commissioning_script_set(
        machine
    )
    result = commissioning_set.scriptresult_set.get(
        script_name=COMMISSIONING_OUTPUT_NAME
    )
    result.store_result(exit_status=0, output=lxd_info, stdout=lxd_info)
    machine.current_commissioning_script_set = commissioning_set

    testing_set = ScriptSet.objects.create_testing_script_set(machine)
    machine.current_testing_script_set = testing_set

    if machine.status in (
        NODE_STATUS.DEPLOYING,
        NODE_STATUS.DEPLOYED,
        NODE_STATUS.FAILED_DEPLOYMENT,
    ):
        install_set = ScriptSet.objects.create_installation_script_set(machine)
        machine.current_installation_script_set = install_set
    machine.save()
