#!/usr/bin/env python3

import argparse
import os
from pathlib import Path
import re
from shutil import which
from subprocess import Popen
import sys

from redbaron import RedBaron
from redbaron.nodes import ClassNode, CommentNode, FromImportNode

IGNORED_DIRS = ("maas-offline-docs", "maasui", "host-info", "maas.egg-info", "__pycache__")


def get_target_root():
    return Path(__file__).parent.parent.joinpath("src/")


API_HANDLER_DIRS = (str(get_target_root().joinpath("maasserver/api").resolve()),)
FORMS_DIRS = (str(get_target_root().joinpath("maasserver/forms").resolve()),)
MODEL_DIRS = (
    str(get_target_root().joinpath("maasserver/models").resolve()),
    str(get_target_root().joinpath("metadataserver/models").resolve()),
)
WEBSOCKET_HANDLER_DIRS = (str(get_target_root().joinpath("maasserver/websockets/handlers").resolve()),)
POWER_DRIVER_DIRS = (str(get_target_root().joinpath("provisioningserver/drivers/power").resolve()),)
SIGNALS_DIRS = (str(get_target_root().joinpath("maasserver/models/signals").resolve()),)
RPC_DIRS = (
    str(get_target_root().joinpath("maasserver/rpc").resolve()),
    str(get_target_root().joinpath("maasserver/clusterrpc").resolve()),
    str(get_target_root().joinpath("provisioningserver/rpc").resolve()),
)
VIEWS_DIRS = (
    str(get_target_root().joinpath("maasserver/views").resolve()),
)


global verbose 


def verbose_print(msg):
    global verbose
    if verbose:
        print(msg)


def move_maasserver_migrations(file_name):
    return []


def move_metadataserver_migrations(file_name):
    return []


def move_maasperf(file_name):
    # NO-OP
    return []


def move_websocket_base(file_name):
    return [
        (str(Path(file_name).joinpath("base.py").resolve()), str(get_target_root().joinpath("websockets/base.py").resolve())),
        (str(Path(file_name).joinpath("protocol.py").resolve()), str(get_target_root().joinpath("websockets/protocol.py").resolve())),
        (str(Path(file_name).joinpath("websockets.py").resolve()), str(get_target_root().joinpath("websockets/websockets.py").resolve())),
        (str(Path(file_name).joinpath("tests/test_base.py").resolve()), str(get_target_root().joinpath("websockets/tests/test_base.py").resolve())),
        (str(Path(file_name).joinpath("tests/test_protocol.py").resolve()), str(get_target_root().joinpath("websockets/tests/test_protocol.py").resolve())),
        (str(Path(file_name).joinpath("tests/test_websockets.py").resolve()), str(get_target_root().joinpath("websockets/tests/test_websockets.py").resolve())),
    ]


def split_up_forms_init_file(file_name):
    return []

def split_up_models_init_file(file_name):
    return []


def _write_red_baron_file(dir_name, file_name, code):
    dir_path = get_target_root().joinpath(dir_name).resolve()
    file_path = dir_path.joinpath(file_name).resolve()
    if not os.path.exists(str(dir_path)):
        os.makedirs(dir_path)

    with open(str(file_path), "w+") as f:
        f.write(code.dumps())
    return str(file_path)


def _remove_unrelated_code(preserve_blocks, code):
    return code.filter(lambda x: type(x) != ClassNode or x.name in preserve_blocks)


def split_up_bmc_models(file_name):
    bmc_code_blocks = ("BaseBMCManager", "BMCManager", "BMC", "BMCRoutableRackControllerRelationship")
    pod_code_blocks = ("PodManager", "Pod")
    with open(file_name) as f:
        bmc_src = RedBaron(f.read())
        # make a copy for the pod classes
        pod_src = bmc_src.copy()
    bmc_src = _remove_unrelated_code(bmc_code_blocks, bmc_src)
    pod_src = _remove_unrelated_code(pod_code_blocks, pod_src)
    return [
        ("-", file_name),
        ("+", _write_red_baron_file("bmc", "bmc.py", bmc_src)),
        ("+", _write_red_baron_file("vmhost", "pod.py", pod_src)),
    ]


def move_metadataserver_models_init_file(file_name):
    # TODO handle old package level loggers
    return [
        ("-", file_name)
    ]


def move_maasserver_init_file(file_name):
    return []


def move_utils_init_file(file_name):
    return []


def move_triggers_init_file(file_name):
    return [
        (
            file_name,
            str(get_target_root().joinpath("triggers/__init__.py")),
        )
    ]


def move_maasserver_root_tests(file_name):
    return []


def move_maasserver_testing(file_name):
    return []


def drop_pluralization(parent):
    def _inner(file_name):
        f = str(file_name).lower().split(".")
        base = f[0]
        if base.endswith("s"):
            base = base[0:-2]
            return [(file_name, create_destination(".".join([base, f[1]]), parent))]
    return _inner


def split_node_model(file_name):
    node_code_blocks = (
        "NodeManager",
        "Node",
        "NodeQueriesMixin",
        "NodeQuerySet",
        "BaseNodeManager",
        "GeneralManager",
        "_clone_object",
        "get_bios_boot_from_bmc",
    )
    machine_code_blocks = ("Machine", "MachineManager")
    device_code_blocks = ("Device", "DeviceManager")
    controller_code_blocks = ("RegionControllerManager", "Controller", "RackController", "RegionController")
    with open(file_name) as f:
        node_src = RedBaron(f.read())
        # make a copy for the other components
        machine_src = node_src.copy()
        device_src = node_src.copy()
        controller_src = node_src.copy()
    node_src = _remove_unrelated_code(node_code_blocks, node_src)
    machine_src = _remove_unrelated_code(machine_code_blocks, machine_src)
    device_src = _remove_unrelated_code(device_code_blocks, device_src)
    controller_src = _remove_unrelated_code(controller_code_blocks, controller_src)
    return [
        ("-", file_name),
        ("+", _write_red_baron_file("node", "node.py", node_src)),
        ("+", _write_red_baron_file("machine", "machine.py", machine_src)),
        ("+", _write_red_baron_file("device", "device.py", device_src)),
        ("+", _write_red_baron_file("controller", "controller", controller_src))
    ]


def move_power_registry_file(file_name):
    return [(file_name, str(get_target_root().joinpath("power_drivers/registry.py").resolve()))]


def move_power_test_registry_file(file_name):
    return [(file_name, str(get_target_root().joinpath("power_drivers/tests/test_registr.py").resolve()))]


SPECIAL_CASE_DIRS = {
    get_target_root().joinpath("maasperf").resolve(): move_maasperf,
    get_target_root().joinpath("maasserver/migrations").resolve(): move_maasserver_migrations,
    get_target_root().joinpath("metadataserver/migrations").resolve(): move_metadataserver_migrations,
    get_target_root().joinpath("maasserver/websockets").resolve(): move_websocket_base,
    get_target_root().joinpath("maasserver/tests").resolve(): move_maasserver_root_tests,
    get_target_root().joinpath("maasserver/testing").resolve(): move_maasserver_testing,
}


SPECIAL_CASE_FILES = {
    get_target_root().joinpath("maasserver/__init__.py").resolve(): move_maasserver_init_file,
    get_target_root().joinpath("maasserver/forms/__init__.py").resolve(): split_up_forms_init_file,
    get_target_root().joinpath("maasserver/models/__init__.py").resolve(): split_up_models_init_file,
    get_target_root().joinpath("maasserver/utils/__init__.py").resolve(): move_utils_init_file,
    get_target_root().joinpath("maasserver/triggers/__init__.py").resolve(): move_triggers_init_file,
    get_target_root().joinpath("maasserver/models/bmc.py").resolve(): split_up_bmc_models,
    get_target_root().joinpath("metadataserver/models/__init__.py").resolve(): move_metadataserver_models_init_file,
    get_target_root().joinpath("maasserver/api/interfaces.py").resolve(): drop_pluralization("maasserver/api"),
    get_target_root().joinpath("maasserver/models/node.py").resolve(): split_node_model,
    get_target_root().joinpath("provisioningserver/drivers/power/registry.py").resolve(): move_power_registry_file,
    get_target_root().joinpath("provisioningserver/drivers/power/tests/test_registry.py").resolve(): move_power_test_registry_file,
}


def generate_base_dir_name(root, file_name):
    file_name = str(file_name)
    root = str(root)
    if root[-1] != "/":
        root += "/"
    base_name = file_name.replace(root, "").split(".")[0]
    if base_name.startswith("test_"):
        return base_name.replace("test_", "")
    return base_name


def create_destination(file_name, parent=""):
    file_name = str(file_name)
    parent = str(parent)
    if file_name.endswith("__init__.py") and os.stat(file_name).st_size == 0:
        return ""
    if parent.endswith("tests/") or parent.endswith("tests"):
        if parent[-1] == "/":
            parent = parent[:-2]
        grandparent = parent.replace("/tests", "")
        base_name = generate_base_dir_name(parent, file_name)
        if grandparent in MODEL_DIRS:
            return get_target_root().joinpath(f"{base_name}/tests/{file_name}")
        if grandparent in API_HANDLER_DIRS:
            return get_target_root().joinpath(f"{base_name}/tests/test_api_handler.py")
        if grandparent in WEBSOCKET_HANDLER_DIRS:
            return get_target_root().joinpath(f"{base_name}/tests/test_ws_handler.py")
        if grandparent in FORMS_DIRS:
            return get_target_root().joinpath(f"{base_name}/tests/test_forms.py")
        if grandparent in POWER_DRIVER_DIRS:
            return get_target_root().joinpath(f"{base_name}/tests/test_driver.py")
        if grandparent in RPC_DIRS:
            return get_target_root().joinpath(f"{base_name}/tests/test_rpc_handler.py")
    if parent in MODEL_DIRS:
        return get_target_root().joinpath(f"{generate_base_dir_name(parent, file_name)}/{str(file_name).replace(str(parent), '')}").resolve()
    if parent in API_HANDLER_DIRS:
        return get_target_root().joinpath(f"{generate_base_dir_name(parent, file_name)}/api_handler.py").resolve()
    if parent in WEBSOCKET_HANDLER_DIRS:
        return get_target_root().joinpath(f"{generate_base_dir_name(parent, file_name)}/ws_handler.py").resolve()
    if parent in FORMS_DIRS:
        return get_target_root().joinpath(f"{generate_base_dir_name(parent, file_name)}/forms.py").resolve()
    if parent in POWER_DRIVER_DIRS:
        return get_target_root().joinpath(f"{generate_base_dir_name(parent, file_name)}/driver.py").resolve()
    if parent in RPC_DIRS:
        if "maasserver" in parent:
            return get_target_root().joinpath(f"{generate_base_dir_name(parent, file_name)}/region_rpc_handler.py")
        return get_target_root().joinpath(f"{generate_base_dir_name(parent, file_name)}/rack_rpc_handler.py").resolve()
    return file_name


def load_layout_changes():
    
    def _walk(root, changes):
        child_dirs = []
        
        verbose_print(f"scanning {root}")
    
        if root in SPECIAL_CASE_DIRS:
            changes += SPECIAL_CASE_DIRS[root](root)
            return []

        with os.scandir(root) as scanner:
            for entry in scanner:
                if not entry.name.startswith(".") and entry.is_file():
                    name = Path(root).joinpath(entry.name).resolve()
                    verbose_print(f"generating new path for: {name}")
                    if name in SPECIAL_CASE_FILES:
                        changes += SPECIAL_CASE_FILES[name](name)
                    else:
                        changes.append((name, create_destination(name, parent=root)))
                if entry.is_dir() and entry.name not in IGNORED_DIRS:
                    child_dirs.append(Path(root).joinpath(entry.name).resolve())
        return child_dirs

    dirs = [get_target_root().resolve()]
    changes = []
    while len(dirs) > 0:
        dirs = [ child for d in dirs for child in _walk(d, changes) ]
    return changes


def move_files(changes, dry_run=False):
    git_cmd = which("git")
    for change in changes:
        # check if destination already exists
        try:
            os.stat(change[1])
        except FileNotFoundError:
            proc = None
            if change[0] == "+": # new file from split out
                proc = Popen([git_cmd, "add", change[1]])
            elif change[1] == "-": # old file from split out
                proc = Popen([git_cmd, "rm", change[0]])
            else:
                proc = Popen([git_cmd, "mv", change[0], change[1]])
            proc.wait()
            if proc.returncode != 0:
                # TODO handle unsuccessful git mv
                pass
        else:
            # handle name collission
            pass
    

SPECIAL_CASE_IMPORTS = {
    str(get_target_root().joinpath("bmc/bmc.py").resolve()): ("maasserver.models.bmc.BMC*", "bmc.BMC*"),
    str(get_target_root().joinpath("vmhost/pod.py").resolve()): ("maasserver.models.bmc.Pod*", "vmhost.Pod*"),
}


def _format_import_from_path(path):
    path = str(path).replace(str(get_target_root().resolve()) + "/", "")
    if path.endswith(".py"):
        path = path[:-3]
    path_list = path.split("/")
    return ".".join(path_list)


def _generate_imports(changes):
    return [ (_format_import_from_path(change[0]), _format_import_from_path(change[1])) if change[1] not in SPECIAL_CASE_IMPORTS else SPECIAL_CASE_IMPORTS[change[1]] for change in changes ]


def _find_and_swap_imports(imports, f):
    src = RedBaron(f.read())
    for import_pair in imports:
        lines = src.find_all("import_node", value=lambda v: v in import_pair[0].split("."))
        for line in lines:
            pass


def modify_imports(changes):
    imports = _generate_imports(changes)

    def _modify(file_name):
        with open(file_name) as f:
            new_src = _find_and_swap_imports(imports, f)
            f.write(new_src.dumps())

    return _modify


def diff_imports(changes):
    imports = _generate_imports(changes)

    def _diff(file_name):
        with open(file_name) as f:
            src = RedBaron(f.read())
    
    return _diff


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate to new directory structure")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print out destination paths and import statement diffs, but do not actually modify files",
    )
    parser.add_argument(
        "-v",
        action="store_true",
        help="enable verbose messaging",
    )
   
    args = parser.parse_args()
    verbose = args.v

    changes = load_layout_changes()
    [ print(f"{change[0]} -> {change[1]}") for change in changes if change[1] ]

    confirmation = input("Ok to proceed?\n")
    if not confirmation.lower().startswith("y"):
        sys.exit(0)
    
    if not args.dry_run:
        move_files(changes)
        modify_imports(changes)
    else:
        diff_imports(changes)
