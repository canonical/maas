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

IGNORED_DIRS = (
    "maas-offline-docs",
    "maasui",
    "host-info",
    "maas.egg-info",
    "__pycache__",
)

TARGET_ROOT = Path(__file__).parent.parent / "src"

API_HANDLER_DIR = TARGET_ROOT / "maasserver" / "api"
FORMS_DIR = TARGET_ROOT / "maasserver" / "forms"
MODEL_DIRS = {
    TARGET_ROOT / "maasserver" / "models",
    TARGET_ROOT / "metadataserver" / "models",
}
WEBSOCKET_HANDLER_DIR = TARGET_ROOT / "maasserver" / "websockets" / "handlers"
POWER_DRIVER_DIR = TARGET_ROOT / "provisioningserver" / "drivers" / "power"
SIGNALS_DIR = TARGET_ROOT / "maasserver" / "models" / "signals"
RPC_DIRS = {
    TARGET_ROOT / "maasserver" / "rpc": "region",
    TARGET_ROOT / "maasserver" / "clusterrpc": "region",
    TARGET_ROOT / "provisioningserver" / "rpc": "rack",
}
VIEWS_DIRS = {TARGET_ROOT / "maasserver" / "views"}

global verbose
global dry_run


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


def move_websocket_base(websockets_dir):
    return [
        (
            websockets_dir / "base.py",
            TARGET_ROOT / "websockets" / "base.py",
        ),
        (
            websockets_dir / "protocol.py",
            TARGET_ROOT / "websockets" / "protocol.py",
        ),
        (
            websockets_dir / "websockets.py",
            TARGET_ROOT / "websockets" / "websockets.py",
        ),
        (
            websockets_dir / "tests/test_base.py",
            TARGET_ROOT / "websockets" / "tests" / "test_base.py",
        ),
        (
            websockets_dir / "tests/test_protocol.py",
            TARGET_ROOT / "websockets" / "tests" / "test_protocol.py",
        ),
        (
            websockets_dir / "tests/test_websockets.py",
            TARGET_ROOT / "websockets" / "tests" / "test_websockets.py",
        ),
    ]


def split_up_forms_init_file(file_name):
    return []


def split_up_models_init_file(file_name):
    return []


def _write_red_baron_file(dir_name, file_name, code):
    global dry_run

    dir_path = TARGET_ROOT / dir_name
    file_path = dir_path / file_name
    dir_path.mkdir(parents=True, exist_ok=True)

    if not dry_run:
        with file_path.open("w+") as f:
            f.write(code.dumps())
    return file_path


def _remove_unrelated_code(preserve_blocks, code):
    return code.filter(
        lambda x: type(x) != ClassNode or x.name in preserve_blocks
    )


def split_up_bmc_models(file_name):
    bmc_code_blocks = {
        "BaseBMCManager",
        "BMCManager",
        "BMC",
        "BMCRoutableRackControllerRelationship",
    }
    pod_code_blocks = {"PodManager", "Pod"}
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
    return [("-", file_name)]


def move_maasserver_init_file(file_name):
    return []


def move_utils_init_file(file_name):
    return []


def move_triggers_init_file(file_name):
    return [
        (
            file_name,
            TARGET_ROOT / "triggers" / "__init__.py",
        )
    ]


def move_maasserver_root_tests(file_name):
    return []


def move_maasserver_testing(file_name):
    return []


def drop_pluralization(parent):
    def _inner(file_name):
        stem = file_name.stem
        if stem.endswith("s"):
            singular = file_name.with_stem(stem[:-1])
            return [(file_name, create_destination(singular, parent))]

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
    controller_code_blocks = (
        "RegionControllerManager",
        "Controller",
        "RackController",
        "RegionController",
    )
    with open(file_name) as f:
        node_src = RedBaron(f.read())
        # make a copy for the other components
        machine_src = node_src.copy()
        device_src = node_src.copy()
        controller_src = node_src.copy()
    node_src = _remove_unrelated_code(node_code_blocks, node_src)
    machine_src = _remove_unrelated_code(machine_code_blocks, machine_src)
    device_src = _remove_unrelated_code(device_code_blocks, device_src)
    controller_src = _remove_unrelated_code(
        controller_code_blocks, controller_src
    )
    return [
        ("-", file_name),
        ("+", _write_red_baron_file("node", "node.py", node_src)),
        ("+", _write_red_baron_file("machine", "machine.py", machine_src)),
        ("+", _write_red_baron_file("device", "device.py", device_src)),
        (
            "+",
            _write_red_baron_file(
                "controller", "controller.py", controller_src
            ),
        ),
    ]


def move_power_registry_file(file_name):
    return [
        (
            file_name,
            TARGET_ROOT / "power_drivers" / "registry.py",
        )
    ]


def move_power_test_registry_file(file_name):
    return [
        (
            file_name,
            TARGET_ROOT / "power_drivers" / "tests" / "test_registry.py",
        )
    ]


SPECIAL_CASE_DIRS = {
    TARGET_ROOT / "maasperf": move_maasperf,
    TARGET_ROOT / "maasserver" / "migrations": move_maasserver_migrations,
    TARGET_ROOT
    / "metadataserver"
    / "migrations": move_metadataserver_migrations,
    TARGET_ROOT / "maasserver" / "websockets": move_websocket_base,
    TARGET_ROOT / "maasserver" / "tests": move_maasserver_root_tests,
    TARGET_ROOT / "maasserver" / "testing": move_maasserver_testing,
}


SPECIAL_CASE_FILES = {
    TARGET_ROOT / "maasserver" / "__init__.py": move_maasserver_init_file,
    TARGET_ROOT
    / "maasserver"
    / "forms"
    / "__init__.py": split_up_forms_init_file,
    TARGET_ROOT
    / "maasserver"
    / "models"
    / "__init__.py": split_up_models_init_file,
    TARGET_ROOT / "maasserver" / "utils" / "__init__.py": move_utils_init_file,
    TARGET_ROOT
    / "maasserver"
    / "triggers"
    / "__init__.py": move_triggers_init_file,
    TARGET_ROOT / "maasserver" / "models" / "bmc.py": split_up_bmc_models,
    TARGET_ROOT
    / "metadataserver"
    / "models"
    / "__init__.py": move_metadataserver_models_init_file,
    TARGET_ROOT
    / "maasserver"
    / "api"
    / "interfaces.py": drop_pluralization(Path("maasserver/api")),
    TARGET_ROOT / "maasserver" / "models" / "node.py": split_node_model,
    TARGET_ROOT
    / "provisioningserver"
    / "drivers"
    / "power"
    / "registry.py": move_power_registry_file,
    TARGET_ROOT
    / "provisioningserver"
    / "drivers"
    / "power"
    / "tests"
    / "test_registry.py": move_power_test_registry_file,
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


def create_destination(file_path, parent):
    file_name = str(file_path)
    if file_path.name == "__init__.py" and file_path.stat().st_size == 0:
        return Path()
    if parent.name == "tests":
        grandparent = parent.parent
        base_name = generate_base_dir_name(parent, file_name)
        if grandparent in MODEL_DIRS:
            return TARGET_ROOT / base_name / "tests" / file_path.name
        if grandparent == API_HANDLER_DIR:
            return TARGET_ROOT / base_name / "tests" / "test_api_handler.py"
        if grandparent == WEBSOCKET_HANDLER_DIR:
            return TARGET_ROOT / base_name / "tests" / "test_ws_handler.py"
        if grandparent == FORMS_DIR:
            return TARGET_ROOT / base_name / "tests" / "test_forms.py"
        if grandparent == POWER_DRIVER_DIR:
            return TARGET_ROOT / base_name / "tests" / "test_driver.py"
        if grandparent in RPC_DIRS:
            return TARGET_ROOT / base_name / "tests" / "test_rpc_handler.py"
    if parent in MODEL_DIRS:
        return (
            TARGET_ROOT
            / generate_base_dir_name(parent, file_name)
            / file_path.name
        )
    if parent == API_HANDLER_DIR:
        return (
            TARGET_ROOT
            / generate_base_dir_name(parent, file_name)
            / "api_handler.py"
        )
    if parent == WEBSOCKET_HANDLER_DIR:
        return (
            TARGET_ROOT
            / generate_base_dir_name(parent, file_name)
            / "ws_handler.py"
        )
    if parent == FORMS_DIR:
        return (
            TARGET_ROOT
            / generate_base_dir_name(parent, file_name)
            / "forms.py"
        )
    if parent == POWER_DRIVER_DIR and file_path.stem == ".py":
        return (
            TARGET_ROOT
            / generate_base_dir_name(parent, file_name)
            / "driver.py"
        )
    if parent in RPC_DIRS:
        if "maasserver" in parent.parts:
            return (
                TARGET_ROOT
                / generate_base_dir_name(parent, file_name)
                / "region_rpc_handler.py"
            )
        return (
            TARGET_ROOT
            / generate_base_dir_name(parent, file_name)
            / "rack_rpc_handler.py"
        )
    return file_path


def load_layout_changes():
    def _walk(root, changes):
        child_dirs = []

        verbose_print(f"scanning {root}")

        if root in SPECIAL_CASE_DIRS:
            changes += SPECIAL_CASE_DIRS[root](root)

        with os.scandir(root) as scanner:
            for entry in scanner:
                if not entry.name.startswith(".") and entry.is_file():
                    name = root / entry.name
                    verbose_print(f"generating new path for {name}")
                    if name in SPECIAL_CASE_FILES:
                        changes += SPECIAL_CASE_FILES[name](name)
                    else:
                        changes.append(
                            (name, create_destination(name, parent=root))
                        )
                if entry.is_dir() and entry.name not in IGNORED_DIRS:
                    child_dirs.append(root / entry.name)
        return child_dirs

    dirs = [TARGET_ROOT]
    changes = []
    while len(dirs) > 0:
        dirs = [child for d in dirs for child in _walk(d, changes)]
    return changes


def move_files(changes, dry_run=False):
    git_cmd = which("git")
    for change in changes:
        # check if destination already exists
        try:
            os.stat(change[1])
        except FileNotFoundError:
            proc = None
            if change[0] == "+":  # new file from split out
                proc = Popen([git_cmd, "add", change[1]])
            elif change[1] == "-":  # old file from split out
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
    TARGET_ROOT / "bmc" / "bmc.py": ("maasserver.models.bmc.BMC*", "bmc.BMC*"),
    TARGET_ROOT
    / "vmhost"
    / "pod.py": ("maasserver.models.bmc.Pod*", "vmhost.Pod*"),
}


def _format_import_from_path(path: Path):
    if path.is_relative_to(TARGET_ROOT):
        components = path.relative_to(TARGET_ROOT).with_name(path.stem).parts
        return ".".join(components)


def _generate_imports(changes):
    for old, new in changes:
        if old in {"-", "+"}:
            continue
        if new in SPECIAL_CASE_IMPORTS:
            yield SPECIAL_CASE_IMPORTS[new]
        else:
            old_import = _format_import_from_path(old)
            new_import = _format_import_from_path(new)
            if not new_import:
                continue
            yield (old_import, new_import)


def _find_and_swap_imports(imports, f):
    src = RedBaron(f.read())
    for import_pair in imports:
        lines = src.find_all(
            "import_node", value=lambda v: v in import_pair[0].split(".")
        )
        for line in lines:
            pass


def modify_imports(changes):
    imports = _generate_imports(changes)

    def _modify(file_name):
        with open(file_name) as f:
            new_src = _find_and_swap_imports(imports, f)
            f.write(new_src.dumps())

    for original, new in changes:
        _modify(new)


def diff_imports(changes):
    imports = _generate_imports(changes)

    def _diff(file_name):
        with open(file_name) as f:
            new_src = _find_and_swap_imports(imports, f)
            # src = RedBaron(f.read())

    return "TODO: Diff imports"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrate to new directory structure"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print out destination paths and import statement diffs, but do not actually modify files",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="enable verbose messaging",
    )

    args = parser.parse_args()
    verbose = args.verbose
    dry_run = args.dry_run

    changes = load_layout_changes()
    [
        print(f"{change[0]} -> {change[1]}")
        for change in changes
        if change[1] and change[0] != change[1]
    ]

    if not args.dry_run:
        confirmation = input("OK to proceed?\n")
        if not confirmation.lower().startswith("y"):
            sys.exit("Aborted at user request")

        move_files(changes, dry_run)
        modify_imports(changes)
    else:
        print(diff_imports(changes))
