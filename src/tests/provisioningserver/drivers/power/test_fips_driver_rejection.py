#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Unit tests for FIPS-unsupported power driver rejection."""

from unittest.mock import patch

import pytest

from provisioningserver.drivers.power import apc as apc_module
from provisioningserver.drivers.power import dli as dli_module
from provisioningserver.drivers.power import eaton as eaton_module
from provisioningserver.drivers.power import moonshot as moonshot_module
from provisioningserver.drivers.power import msftocs as msftocs_module
from provisioningserver.drivers.power import raritan as raritan_module
from provisioningserver.drivers.power import recs as recs_module
from provisioningserver.drivers.power import seamicro as seamicro_module
from provisioningserver.drivers.power import ucsm as ucsm_module
from provisioningserver.drivers.power.fips import FIPSDriverUnsupportedError

UNSUPPORTED_DRIVERS = [
    pytest.param(
        apc_module.APCPowerDriver,
        {
            "power_address": "10.0.0.1",
            "node_outlet": "1",
            "power_on_delay": "0",
            "pdu_type": apc_module.APC_PDU_TYPE.RPDU,
        },
        "power_query",
        id="apc",
    ),
    pytest.param(
        eaton_module.EatonPowerDriver,
        {
            "power_address": "10.0.0.1",
            "node_outlet": "1",
            "power_on_delay": "0",
        },
        "power_query",
        id="eaton",
    ),
    pytest.param(
        raritan_module.RaritanPowerDriver,
        {
            "power_address": "10.0.0.1",
            "node_outlet": "1",
            "power_on_delay": "0",
        },
        "power_query",
        id="raritan",
    ),
    pytest.param(
        dli_module.DLIPowerDriver,
        {
            "outlet_id": "1",
            "power_address": "10.0.0.1",
            "power_user": "user",
            "power_pass": "pass",
        },
        "_query_outlet_state",
        id="dli",
    ),
    pytest.param(
        msftocs_module.MicrosoftOCSPowerDriver,
        {
            "power_address": "10.0.0.1",
            "power_port": "8000",
            "power_user": "user",
            "power_pass": "pass",
            "blade_id": "1",
        },
        "power_query",
        id="msftocs",
    ),
    pytest.param(
        recs_module.RECSPowerDriver,
        {
            "power_address": "10.0.0.1",
            "power_port": "8000",
            "power_user": "user",
            "power_pass": "pass",
            "node_id": "1",
        },
        "set_boot_source_recs",
        id="recs",
    ),
    pytest.param(
        seamicro_module.SeaMicroPowerDriver,
        {
            "power_address": "10.0.0.1",
            "power_user": "user",
            "power_pass": "pass",
            "system_id": "1",
            "power_control": "ipmi",
        },
        "_power",
        id="seamicro",
    ),
    pytest.param(
        ucsm_module.UCSMPowerDriver,
        {
            "power_address": "http://10.0.0.1",
            "power_user": "user",
            "power_pass": "pass",
            "uuid": "1234",
        },
        None,
        id="ucsm",
    ),
    pytest.param(
        moonshot_module.MoonshotIPMIPowerDriver,
        {
            "power_address": "10.0.0.1",
            "power_user": "user",
            "power_pass": "pass",
            "power_hwaddress": "0x20 0x02",
        },
        "_issue_ipmitool_command",
        id="moonshot",
    ),
]


class TestFIPSDriverRejection:
    @pytest.mark.parametrize(
        "driver_cls,context,guard_method", UNSUPPORTED_DRIVERS
    )
    def test_power_on_rejected_in_fips_mode(
        self, driver_cls, context, guard_method
    ) -> None:
        driver = driver_cls()

        with patch(
            "provisioningserver.drivers.power.fips.is_fips_enabled",
            return_value=True,
        ):
            if guard_method is not None:
                with patch.object(
                    driver,
                    guard_method,
                    side_effect=AssertionError(
                        f"{guard_method} should not run"
                    ),
                ):
                    with pytest.raises(FIPSDriverUnsupportedError) as exc_info:
                        driver.power_on("system-id", context)
            else:
                with pytest.raises(FIPSDriverUnsupportedError) as exc_info:
                    driver.power_on("system-id", context)

        assert driver.name in str(exc_info.value)
