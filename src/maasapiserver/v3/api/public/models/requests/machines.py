# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from pydantic import BaseModel, Field

from maasapiserver.v3.api.public.models.requests.base import NamedBaseModel


class MachineRequest(NamedBaseModel):
    # TODO
    pass


class MachineCommissionRequest(BaseModel):
    enable_ssh: bool = Field(
        default=False,
        description="Allow SSH access into the commissioning environment by using the requesting user's SSH key(s) and preventing machine power off after commissioning has completed.",
    )
    skip_bmc_config: bool = Field(
        default=False,
        description="Skip configuring the machine's BMC.",
    )
    skip_networking: bool = Field(
        default=False,
        description="Skip configuring the machine's networking during commissioning.",
    )
    skip_storage: bool = Field(
        default=False,
        description="Skip configuring the machine's storage during commissioning.",
    )
    commissioning_scripts: list[str] | None = Field(
        default=None,
        description="List of names, tags or IDs of commissioning scripts to "
        "run. By default all commissioning scripts are run, except those "
        "tagged 'noauto' or restricted to specific hardware. Built-in "
        "commissioning scripts always run. Use 'none' on its own to run only "
        "the built-in scripts. Scripts restricted to specific hardware, such "
        "as those tagged 'update_firmware' or 'configure_hba', only run on "
        "matching machines.",
    )
    testing_scripts: list[str] | None = Field(
        default=None,
        description="List of names, tags or IDs of testing scripts to run after "
        "commissioning. By default all tests tagged 'commissioning' are run. "
        "Use 'none' on its own to disable running tests.",
    )
    script_input: dict[str, dict[str, Any]] | None = Field(
        default=None,
        description="Parameter values for the selected commissioning and "
        "testing scripts, keyed by script name and then by parameter name. "
        "Input for scripts that are not selected is rejected. For example: "
        '{"smartctl-validate": {"storage": "sda,sdb"}, '
        '"internet-connectivity": {"url": "https://archive.ubuntu.com"}}',
    )
