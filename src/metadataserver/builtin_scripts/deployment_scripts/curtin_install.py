#!/usr/bin/env python3

# curtin-install - Download curtin from the region and run it.
#
# Author: Jacopo Rota <jacopo.rota@canonical.com>
#
# Copyright (C) 2025 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# --- Start MAAS 1.0 script metadata ---
# name: 50-curtin-install
# title: Download curtin from the region and run it.
# description: Download curtin from the region and run it.
# script_type: deployment
# timeout: 01:30:00
# --- End MAAS 1.0 script metadata ---

import os
import stat
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid

import yaml

CFG_FILE = "/etc/cloud/cloud.cfg.d/91_kernel_cmdline_url.cfg"
INSTALLER = "curtin-installer"


class CurtinInstallError(Exception):
    pass


def load_cloud_cfg(path):
    if not os.path.isfile(path):
        raise CurtinInstallError(
            "Cloud-init config file not found: {path}".format(path=path)
        )

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def extract_maas_config(cfg):
    try:
        maas = cfg["datasource"]["MAAS"]
        return {
            "consumer_key": maas["consumer_key"],
            "token_key": maas["token_key"],
            "token_secret": maas["token_secret"],
            "metadata_url": maas["metadata_url"],
        }
    except (KeyError, TypeError) as e:
        raise CurtinInstallError("Failed to extract MAAS configuration") from e


def get_maas_base_url(metadata_url):
    if not metadata_url:
        raise CurtinInstallError("metadata_url is empty")

    return metadata_url.replace("/MAAS/metadata/curtin", "")


def build_auth_header(consumer_key, token_key, token_secret) -> str:
    nonce = str(uuid.uuid4())
    timestamp = str(int(time.time()))

    return (
        "OAuth "
        "oauth_version=1.0, "
        "oauth_signature_method=PLAINTEXT, "
        "oauth_consumer_key={consumer_key}, "
        "oauth_token={token_key}, "
        "oauth_signature=&{token_secret}, "
        "oauth_nonce={nonce}, "
        "oauth_timestamp={timestamp}".format(
            consumer_key=consumer_key,
            token_key=token_key,
            token_secret=token_secret,
            nonce=nonce,
            timestamp=timestamp,
        )
    )


def download_installer(url, auth_header, output_path):
    req = Request(url, headers={"Authorization": auth_header})

    try:
        with urlopen(req) as resp, open(output_path, "wb") as out:
            data = resp.read()
            if not data:
                raise CurtinInstallError("Downloaded installer is empty")
            out.write(data)
    except HTTPError as e:
        raise CurtinInstallError(
            "HTTP error {code}".format(code=e.code)
        ) from e
    except URLError as e:
        raise CurtinInstallError(
            "Network error: {reason}".format(reason=e.reason)
        ) from e


def make_executable(path):
    st = os.stat(path)
    os.chmod(path, st.st_mode | stat.S_IXUSR)


def run_installer(path):
    try:
        subprocess.run([path], check=True)
    except Exception as e:
        raise CurtinInstallError("Curtin installer exited with errors") from e


def main():
    print("INFO: Extracting node credentials..", flush=True)

    cfg = load_cloud_cfg(CFG_FILE)
    maas = extract_maas_config(cfg)

    maas_url = get_maas_base_url(maas["metadata_url"])

    auth_header = build_auth_header(
        maas["consumer_key"],
        maas["token_key"],
        maas["token_secret"],
    )

    installer_url = (
        "{maas_url}/MAAS/metadata/curtin/2012-03-01/curtin-installer".format(
            maas_url=maas_url
        )
    )

    print(
        "INFO: Downloading curtin installer from {maas_url}...".format(
            maas_url=maas_url
        ),
        flush=True,
    )
    download_installer(installer_url, auth_header, INSTALLER)

    make_executable(INSTALLER)

    print("INFO: Running curtin installer...", flush=True)
    run_installer("./{installer}".format(installer=INSTALLER))


if __name__ == "__main__":
    main()
