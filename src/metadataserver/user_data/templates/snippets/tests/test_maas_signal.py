# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from importlib import import_module
import io
import sys
from unittest.mock import patch

from maastesting.testcase import MAASTestCase
from snippets import maas_api_helper


class TestSignal(MAASTestCase):
    def setUp(self):
        super().setUp()
        with patch.dict(sys.modules, {"maas_api_helper": maas_api_helper}):
            self.maas_signal = import_module("snippets.maas_signal")
        self.mock_signal = self.patch(self.maas_signal, "signal")

    def test_rejects_wedge_power_type(self):
        self.patch(
            sys,
            "argv",
            [
                "maas-signal",
                "--url",
                "http://maas.example.com",
                "--power-type",
                "wedge",
                "OK",
            ],
        )
        stderr = self.patch(sys, "stderr", io.StringIO())

        error = self.assertRaises(SystemExit, self.maas_signal.main)

        self.assertEqual(2, error.code)
        self.assertIn("invalid choice: 'wedge'", stderr.getvalue())
        self.mock_signal.assert_not_called()

    def test_signals_supported_power_types(self):
        for power_type in ("ipmi", "virsh", "manual", "moonshot"):
            self.patch(
                sys,
                "argv",
                [
                    "maas-signal",
                    "--url",
                    "http://maas.example.com",
                    "--power-type",
                    power_type,
                    "OK",
                ],
            )

            self.maas_signal.main()

            self.mock_signal.assert_called_once()
            self.assertEqual(
                (power_type, None), self.mock_signal.call_args.args[-2:]
            )
            self.mock_signal.reset_mock()
