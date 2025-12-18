# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import io
import os
import time
import uuid

import yaml

from maastesting.testcase import MAASTestCase
import metadataserver.builtin_scripts.deployment_scripts.curtin_install as ci

VALID_CFG = {
    "datasource": {
        "MAAS": {
            "consumer_key": "ck",
            "token_key": "tk",
            "token_secret": "ts",
            "metadata_url": "http://maas/MAAS/metadata/curtin",
        }
    }
}


class TestCurtinInstall(MAASTestCase):
    def test_extract_maas_config_success(self):
        maas = ci.extract_maas_config(VALID_CFG)
        self.assertEqual("ck", maas["consumer_key"])
        self.assertEqual("tk", maas["token_key"])
        self.assertEqual("ts", maas["token_secret"])

    def test_extract_maas_config_failure(self):
        self.assertRaises(ci.CurtinInstallError, ci.extract_maas_config, {})

    def test_build_maas_url(self):
        url = ci.get_maas_base_url("http://x/MAAS/metadata/curtin")
        self.assertEqual("http://x", url)

    def test_build_auth_header_deterministic(self):
        self.patch(time, "time", lambda: 123)
        self.patch(
            uuid, "uuid4", lambda: "00000000-0000-0000-0000-000000000000"
        )
        header = ci.build_auth_header(
            "ck",
            "tk",
            "ts",
        )
        self.assertIn("oauth_consumer_key=ck", header)
        self.assertIn("oauth_token=tk", header)
        self.assertIn("oauth_signature=&ts", header)
        self.assertIn("oauth_timestamp=123", header)
        self.assertIn(
            "oauth_nonce=00000000-0000-0000-0000-000000000000", header
        )

    def test_download_installer_success(self):
        fake_resp = io.BytesIO(b"binarydata")
        fake_resp.__enter__ = lambda s: s
        fake_resp.__exit__ = lambda *a: None

        tmpdir = self.make_dir()

        urlopen_mock = self.patch(ci, "urlopen")
        urlopen_mock.return_value = fake_resp

        out = os.path.join(tmpdir, "installer")
        ci.download_installer("http://x", "auth", out)

        with open(out, "rb") as f:
            self.assertEqual(b"binarydata", f.read())

    def test_download_installer_empty(self):
        fake_resp = io.BytesIO(b"")
        fake_resp.__enter__ = lambda s: s
        fake_resp.__exit__ = lambda *a: None

        urlopen_mock = self.patch(ci, "urlopen")
        urlopen_mock.return_value = fake_resp

        tmpdir = self.make_dir()
        out = os.path.join(tmpdir, "installer")
        self.assertRaises(
            ci.CurtinInstallError,
            ci.download_installer,
            "http://x",
            "auth",
            out,
        )

    def test_run_installer_success(self):
        subprocess_mock = self.patch(ci.subprocess, "run")
        subprocess_mock.return_value = None
        ci.run_installer("./installer")
        subprocess_mock.assert_called_once_with(["./installer"], check=True)

    def test_run_installer_failure(self):
        subprocess_mock = self.patch(ci.subprocess, "run")
        subprocess_mock.side_effect = Exception("boom")
        self.assertRaises(
            ci.CurtinInstallError,
            ci.run_installer,
            "./installer",
        )

    def test_script_flow(self):
        tmpfile = self.make_file(contents=yaml.dump(VALID_CFG))

        fake_installer_data = b"#!/bin/sh\necho curtin\n"

        fake_resp = io.BytesIO(fake_installer_data)
        fake_resp.__enter__ = lambda s: s
        fake_resp.__exit__ = lambda *a: None

        self.patch(ci, "CFG_FILE", tmpfile)

        urlopen_mock = self.patch(ci, "urlopen")
        urlopen_mock.return_value = fake_resp

        subprocess_run_mock = self.patch(ci, "subprocess")
        subprocess_run_mock.run.return_value = None

        ci.main()

        urlopen_mock.assert_called_once()

        subprocess_run_mock.run.assert_called_once_with(
            ["./curtin-installer"],
            check=True,
        )
