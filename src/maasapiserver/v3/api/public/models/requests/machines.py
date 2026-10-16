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
        description="List of commissioning script names and tags to be run. By "
        "default all custom commissioning scripts are run. Built-in "
        "commissioning scripts always run. Selecting 'update_firmware' or "
        "'configure_hba' will run firmware updates or configure HBA's on "
        "matching machines.",  # TODO: copied from v2, double check this after script behaviour is confirmed.
    )
    testing_scripts: list[str] | None = Field(
        default=None,
        description="List of names, tags or IDs of testing scripts to run after "
        "commissioning. By default all tests tagged 'commissioning' are run. "
        "Use 'none' to disable running tests.",  # TODO: mostly copied from v2, double check this after script behaviour is confirmed.
    )
    script_input: dict[str, dict[str, Any]] | None = Field(
        default=None,
        description="Parameter values for the selected commissioning and "
        "testing scripts, keyed by script name and then by parameter name. "
        "Input for scripts that are not selected is ignored. For example: "
        '{"smartctl-validate": {"storage": "sda,sdb"}, '
        '"internet-connectivity": {"url": "https://archive.ubuntu.com"}}',
    )
