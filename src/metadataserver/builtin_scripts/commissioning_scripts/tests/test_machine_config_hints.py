# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase

spec = spec_from_loader(
    "machine_hint",
    SourceFileLoader(
        "machine_hint",
        "src/metadataserver/builtin_scripts/commissioning_scripts/40-maas-01-machine-config-hints",
    ),
)
machine_hint = module_from_spec(spec)
spec.loader.exec_module(machine_hint)


class TestMachineHints(MAASTestCase):
    def test_provide_hints_generic(self):
        self.assertEqual(
            {"platform": "generic", "tags": []},
            machine_hint.provide_hints({}),
        )
        self.assertEqual(
            {"platform": "generic", "tags": []},
            machine_hint.provide_hints(
                {"resources": {"system": {"motherboard": None}}}
            ),
        )
        self.assertEqual(
            {"platform": "generic", "tags": []},
            machine_hint.provide_hints(
                {
                    "resources": {
                        "system": {
                            "motherboard": {
                                "vendor": factory.make_string(),
                                "product": factory.make_string(),
                            }
                        }
                    }
                }
            ),
        )

    def test_provide_hints_nvidia(self):
        dgx_res = {
            "resources": {
                "system": {
                    "motherboard": {
                        "vendor": "nvidia",
                        "product": "nvidia dgx",
                    }
                }
            }
        }
        self.assertEqual(
            {"platform": "nvidia-dgx", "tags": []},
            machine_hint.provide_hints(dgx_res),
        )
