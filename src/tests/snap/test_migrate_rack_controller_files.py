#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import os
from pathlib import Path
import subprocess

import pytest

SCRIPT = (
    Path(__file__).parents[3]
    / "snap/local/tree/usr/bin/migrate-rack-controller-files"
)

OLD_CONFIG = """\
controller: https://10.0.0.1:5242
tls:
  key_file: "/snap/common/var/lib/maas/certificates/agent.key"
  cert_file: "/snap/common/var/lib/maas/certificates/agent.crt"
  ca_file: "/snap/common/var/lib/maas/certificates/ca.pem"
"""

NEW_CONFIG = """\
controller: https://10.0.0.1:5242
tls:
  key_file: "/snap/common/var/lib/maas/certificates/rackcontroller.key"
  cert_file: "/snap/common/var/lib/maas/certificates/rackcontroller.crt"
  ca_file: "/snap/common/var/lib/maas/certificates/ca.pem"
"""


class SnapLayout:
    def __init__(self, root: Path):
        self.common = root / "common"
        self.data = root / "data"
        self.common_certs = self.common / "var/lib/maas/certificates"
        self.data_certs = self.data / "certificates"
        self.config_dir = self.common / "etc/maas"
        self.maas_dir = self.common / "maas"
        for directory in (
            self.common_certs,
            self.data_certs,
            self.config_dir,
            self.maas_dir,
        ):
            directory.mkdir(parents=True)

    def run(self) -> None:
        env = os.environ | {
            "SNAP_COMMON": str(self.common),
            "SNAP_DATA": str(self.data),
        }
        subprocess.run([SCRIPT], env=env, check=True)

    def files(self) -> dict[str, str]:
        return {
            str(path.relative_to(self.common.parent)): path.read_text()
            for path in sorted(self.common.parent.rglob("*"))
            if path.is_file()
        }


@pytest.fixture
def layout(tmp_path: Path) -> SnapLayout:
    return SnapLayout(tmp_path / "snap")


def test_migrates_standalone_enrollment_files(layout: SnapLayout) -> None:
    (layout.maas_dir / "agent_uuid").write_text("uuid\n")
    (layout.common_certs / "agent.crt").write_text("cert")
    (layout.common_certs / "agent.key").write_text("key")
    (layout.common_certs / "ca.pem").write_text("ca")
    (layout.config_dir / "agent.yaml").write_text(OLD_CONFIG)

    layout.run()

    assert layout.files() == {
        "common/etc/maas/rackcontroller.yaml": NEW_CONFIG,
        "common/maas/rack_controller_uuid": "uuid\n",
        "common/var/lib/maas/certificates/ca.pem": "ca",
        "common/var/lib/maas/certificates/rackcontroller.crt": "cert",
        "common/var/lib/maas/certificates/rackcontroller.key": "key",
    }


def test_migrates_rackd_supervised_files(layout: SnapLayout) -> None:
    (layout.data_certs / "agent.crt").write_text("cert")
    (layout.data_certs / "agent.key").write_text("key")
    (layout.config_dir / "agent.yaml").write_text(OLD_CONFIG)

    layout.run()

    assert layout.files() == {
        "common/etc/maas/rackcontroller.yaml": NEW_CONFIG,
        "data/certificates/rackcontroller.crt": "cert",
        "data/certificates/rackcontroller.key": "key",
    }


def test_succeeds_without_old_files(layout: SnapLayout) -> None:
    (layout.maas_dir / "rack_controller_uuid").write_text("uuid\n")
    (layout.config_dir / "rackcontroller.yaml").write_text(NEW_CONFIG)

    layout.run()

    assert layout.files() == {
        "common/etc/maas/rackcontroller.yaml": NEW_CONFIG,
        "common/maas/rack_controller_uuid": "uuid\n",
    }


def test_keeps_new_file_when_both_exist(layout: SnapLayout) -> None:
    (layout.maas_dir / "agent_uuid").write_text("old\n")
    (layout.maas_dir / "rack_controller_uuid").write_text("new\n")

    layout.run()

    assert layout.files() == {"common/maas/rack_controller_uuid": "new\n"}


def test_is_idempotent(layout: SnapLayout) -> None:
    (layout.maas_dir / "agent_uuid").write_text("uuid\n")
    (layout.common_certs / "agent.crt").write_text("cert")
    (layout.config_dir / "agent.yaml").write_text(OLD_CONFIG)

    layout.run()
    after_first_run = layout.files()
    layout.run()

    assert layout.files() == after_first_run
