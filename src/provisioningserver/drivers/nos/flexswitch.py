# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Flexswitch NOS Driver."""


from provisioningserver.drivers.nos import NOSDriver


class FlexswitchNOSDriver(NOSDriver):

    name = "flexswitch"
    description = "Flexswitch"
    settings = []

    def is_switch_supported(self, vendor, model):
        if vendor == "accton" and model in ("wedge100", "wedge40"):
            return True
        return False
