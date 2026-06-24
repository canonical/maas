#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.fips import is_fips_enabled
from maascommon.logging.security import log_fips_driver_rejected
from maascommon.workflows.msm import MachinesCountByStatus
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.machines import MachinesRepository
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    FIPSViolationException,
)
from maasservicelayer.exceptions.constants import FIPS_VIOLATION_TYPE
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.bmc import Bmc
from maasservicelayer.models.machines import PciDevice, UsbDevice
from maasservicelayer.services.dnspublications import DNSPublicationsService
from maasservicelayer.services.events import EventsService
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.scriptresult import ScriptResultsService
from maasservicelayer.services.secrets import SecretsService
from provisioningserver.drivers.power import is_power_parameter_set
from provisioningserver.drivers.power.fips import (
    DRIVER_FIPS_REGISTRY,
    DriverFIPSStatus,
    FIPS_ALLOWED_IPMI_CIPHERS,
    get_fips_compliant_alternatives,
)


class MachinesService(NodesService):
    def __init__(
        self,
        context: Context,
        secrets_service: SecretsService,
        dnspublications_service: DNSPublicationsService,
        events_service: EventsService,
        scriptresults_service: ScriptResultsService,
        machines_repository: MachinesRepository,
    ):
        super().__init__(
            context,
            secrets_service,
            events_service,
            scriptresults_service,
            dnspublications_service,
            machines_repository,
        )
        self.machines_repository = machines_repository

    async def list_machine_usb_devices(
        self, system_id: str, page: int, size: int
    ) -> ListResult[UsbDevice]:
        return await self.machines_repository.list_machine_usb_devices(
            system_id=system_id, page=page, size=size
        )

    async def list_machine_pci_devices(
        self, system_id: str, page: int, size: int
    ) -> ListResult[PciDevice]:
        return await self.machines_repository.list_machine_pci_devices(
            system_id=system_id, page=page, size=size
        )

    async def count_machines_by_statuses(self) -> MachinesCountByStatus:
        return await self.machines_repository.count_machines_by_statuses()

    @staticmethod
    def validate_power_parameters_fips(
        power_type: str, power_parameters: dict
    ) -> None:
        """Validate power parameters for FIPS compliance.

        Raises FIPSViolationException when FIPS mode is active and the
        parameters violate FIPS requirements.
        """
        if not is_fips_enabled():
            return

        status, reason = DRIVER_FIPS_REGISTRY.get(
            power_type, (DriverFIPSStatus.COMPLIANT, None)
        )
        if status == DriverFIPSStatus.UNSUPPORTED:
            log_fips_driver_rejected(driver=power_type, reason=reason or "")
            alternatives = get_fips_compliant_alternatives()
            raise FIPSViolationException(
                details=[
                    BaseExceptionDetail(
                        type=FIPS_VIOLATION_TYPE,
                        message=(
                            f"Power driver '{power_type}' is not FIPS-compliant. "
                            f"Reason: {reason}. "
                            f"Supported alternatives: {', '.join(alternatives)}"
                        ),
                    )
                ]
            )

        if power_type == "ipmi":
            # Match the IPMI driver's own "set vs unset" semantics:
            # an absent or empty cipher_suite_id means "use default",
            # and the driver defaults to "17" in FIPS mode (allowed).
            cipher_raw = power_parameters.get("cipher_suite_id")
            if not is_power_parameter_set(cipher_raw):
                pass  # driver will default to "17" in FIPS mode
            elif str(cipher_raw) not in FIPS_ALLOWED_IPMI_CIPHERS:
                allowed = ", ".join(sorted(FIPS_ALLOWED_IPMI_CIPHERS))
                raise FIPSViolationException(
                    details=[
                        BaseExceptionDetail(
                            type=FIPS_VIOLATION_TYPE,
                            message=(
                                f"IPMI cipher suite {cipher_raw!r} is not "
                                f"FIPS-compliant. Allowed: {allowed}."
                            ),
                        )
                    ]
                )

        if power_type in ("webhook", "proxmox", "hmcz"):
            verify_ssl = power_parameters.get("verify_ssl", True)
            if isinstance(verify_ssl, str):
                verify_ssl = verify_ssl.lower() not in ("false", "0", "no")
            if not verify_ssl:
                raise FIPSViolationException(
                    details=[
                        BaseExceptionDetail(
                            type=FIPS_VIOLATION_TYPE,
                            message=(
                                f"SSL verification cannot be disabled for "
                                f"'{power_type}' driver in FIPS mode."
                            ),
                        )
                    ]
                )

    async def set_bmc(
        self, system_id: str, power_type: str, power_parameters: dict
    ) -> Bmc:
        """Update BMC with FIPS pre-flight validation then delegate to parent."""
        self.validate_power_parameters_fips(power_type, power_parameters)
        return await super().set_bmc(system_id, power_type, power_parameters)
