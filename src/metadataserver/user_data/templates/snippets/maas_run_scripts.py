# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
#
# This file is intended to be run with Python 3.6 or above, so it should only
# use features available in that version.

import argparse
from collections import namedtuple
from contextlib import closing
from datetime import timedelta
import http
from io import BytesIO
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
import time
import urllib.error

import yaml

# imports from maas_api_helpers (only used in tests)
# {% comment %}
from snippets.maas_api_helper import (
    capture_script_output,
    Config,
    Credentials,
    encode_multipart_data,
    get_base_url,
    geturl,
    InvalidCredentialsFormat,
    MD_VERSION,
    signal,
)

# {% endcomment %}


class ExitError(Exception):
    """Exception that causes the app to fail with the specified error message."""


class ScriptsPaths:
    def __init__(self, base_path):
        self.scripts = base_path / "scripts"
        self.out = base_path / "out"
        self.downloads = base_path / "downloads"
        self.resources_file = base_path / "resources.json"

    def ensure(self):
        for directory in (self.scripts, self.out, self.downloads):
            if directory.exists():
                shutil.rmtree(directory)
            directory.mkdir()
        self.resources_file.touch()


ScriptRunResult = namedtuple(
    "ScriptRunResult",
    ["exit_status", "status", "error", "runtime", "result_files"],
)


class Script:
    def __init__(self, info, maas_url, paths):
        self.info = info
        self.maas_url = maas_url
        self.paths = paths

    @property
    def command(self):
        return [str(self.paths.scripts / self.info["path"])]

    @property
    def name(self):
        return self.info["name"]

    @property
    def combined_path(self):
        return self.paths.out / self.name

    @property
    def stdout_path(self):
        return self.paths.out / f"{self.name}.out"

    @property
    def stderr_path(self):
        return self.paths.out / f"{self.name}.err"

    @property
    def result_path(self):
        return self.paths.out / f"{self.name}.yaml"

    @property
    def environ(self):
        env = {
            "MAAS_BASE_URL": self.maas_url,
            "MAAS_RESOURCES_FILE": self.paths.resources_file,
            "OUTPUT_COMBINED_PATH": self.combined_path,
            "OUTPUT_STDOUT_PATH": self.stdout_path,
            "OUTPUT_STDERR_PATH": self.stderr_path,
            "RESULT_PATH": self.result_path,
            "DOWNLOAD_PATH": self.paths.downloads,
            "HAS_STARTED": self.info.get("has_started", False),
            "RUNTIME": self.info.get("timeout_seconds"),
        }
        if "bmc_config_path" in self.info:
            env["BMC_CONFIG_PATH"] = self.info["bmc_config_path"]

        environ = os.environ.copy()
        environ.update((key, str(value)) for key, value in env.items())
        return environ

    def should_run(self):
        """Whether the script should be run."""
        return self.info.get(
            "default", False
        ) and "deploy-info" in self.info.get("tags", [])

    def run(self, console_output=False):
        exit_status = 0
        start = time.monotonic()
        proc = subprocess.Popen(
            self.command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.environ,
        )
        try:
            capture_script_output(
                proc,
                self.combined_path,
                self.stdout_path,
                self.stderr_path,
                timeout_seconds=self.info.get("timeout_seconds"),
                console_output=console_output,
            )
        except OSError as e:
            if e.errno != 0:
                exit_status = e.errno
        except subprocess.TimeoutExpired:
            exit_status = 124
        runtime = time.monotonic() - start

        return ScriptRunResult(
            exit_status,
            *self._get_status_and_error(exit_status),
            runtime,
            self._get_result_files(),
        )

    def _get_status_and_error(self, exit_status):
        status = "WORKING"
        error = None
        if exit_status == 124:
            status = "TIMEDOUT"
            error = "Timeout({timeout}) expired on {script}".format(
                timeout=timedelta(seconds=self.info.get("timeout_seconds")),
                script=self.name,
            )
        elif exit_status != 0:
            status = "FAILED"
            error = "Failed to execute {script}: {exit_status}".format(
                script=self.name,
                exit_status=exit_status,
            )
        return status, error

    def _get_result_files(self):
        return {
            path.name: path.read_bytes()
            for path in (
                self.stdout_path,
                self.stderr_path,
                self.combined_path,
                self.result_path,
            )
            if path.exists()
        }


def oauth_token(string):
    """Helper to use as type for OAuth token commandline args."""
    try:
        return Credentials.from_string(string)
    except InvalidCredentialsFormat as e:
        raise argparse.ArgumentTypeError(str(e))


TOKEN_FORMAT = "'consumer-key:token-key:token-secret[:consumer_secret]'"


def add_maas_admin_args(parser):
    """Add arguments for interacting with MAAS as admin."""
    parser.add_argument(
        "maas_url",
        help="MAAS URL",
    )
    parser.add_argument(
        "admin_token",
        type=oauth_token,
        help="Admin user OAuth token, in the {form} form".format(
            form=TOKEN_FORMAT
        ),
    )


def parse_args(args):
    parser = argparse.ArgumentParser(
        description="run MAAS commissioning scripts and report back results"
    )
    parser.add_argument(
        "--debug",
        help="Print verbose debug messages",
        action="store_true",
        default=False,
    )
    subparsers = parser.add_subparsers(
        metavar="ACTION",
        dest="action",
        help="action to perform",
    )
    subparsers.required = True

    get_machine_token = subparsers.add_parser(
        "get-machine-token",
        help="get authentication token for an existing machine from MAAS",
    )
    add_maas_admin_args(get_machine_token)
    get_machine_token.add_argument(
        "system_id",
        help="system ID for the machine to get credentials for",
    )
    get_machine_token.add_argument(
        "token_file",
        help="path for the file to write the token to",
        type=argparse.FileType("w"),
    )

    register_machine = subparsers.add_parser(
        "register-machine",
        help="register the current machine in MAAS and report scripts results",
    )
    add_maas_admin_args(register_machine)
    register_machine.add_argument(
        "--hostname",
        help="machine hostname (by default, use the current hostname)",
    )
    # Hide from help, since this is meant to be used from tests only.
    register_machine.add_argument(
        "--base-dir",
        default=".",
        help=argparse.SUPPRESS,
    )

    report_results = subparsers.add_parser(
        "report-results",
        help="run scripts for the machine and report results to MAAS",
    )
    report_results.add_argument(
        "--config",
        help="cloud-init config with MAAS credentials and endpoint, (e.g. /etc/cloud/cloud.cfg.d/90_dpkg_local_cloud_config.cfg)",
        type=argparse.FileType(),
    )
    report_results.add_argument(
        "--machine-token",
        type=oauth_token,
        help="Machine OAuth token, in the {form} form".format(
            form=TOKEN_FORMAT
        ),
    )
    report_results.add_argument(
        "--metadata-url",
        help="MAAS metadata URL",
    )

    return parser.parse_args(args=args)


def get_config(ns):
    if ns.config:
        with closing(ns.config) as fd:
            conf = yaml.safe_load(fd)["reporting"]["maas"]
    else:
        conf = {}

    data = {}
    credentials = ns.machine_token
    if not credentials:
        data = {
            key: conf.get(key)
            for key in (
                "token_key",
                "token_secret",
                "consumer_key",
                "consumer_secret",
            )
        }

    url = conf.get("endpoint")
    ns_url = getattr(ns, "metadata_url")
    if ns_url is not None:
        url = ns_url
    data["metadata_url"] = url

    return Config(config=data, credentials=credentials)


def fetch_scripts(maas_url, metadata_url, paths, credentials):
    res = geturl(
        metadata_url + "maas-scripts", credentials=credentials, retry=False
    )
    if res.status == http.client.NO_CONTENT:
        raise ExitError("No script returned")

    with tarfile.open(mode="r|*", fileobj=BytesIO(res.read())) as tar:
        tar.extractall(str(paths.scripts))

    with (paths.scripts / "index.json").open() as fd:
        data = json.load(fd)

    return [
        Script(script_info, maas_url, paths)
        for script_info in data["1.0"]["commissioning_scripts"]
    ]


def get_machine_token(maas_url, admin_token, system_id):
    """Return a dict with machine token and MAAS URL."""
    try:
        response = geturl(
            maas_url + "/api/2.0/machines/" + system_id + "/?op=get_token",
            credentials=admin_token,
            retry=False,
        )
    except urllib.error.HTTPError as e:
        raise ExitError(
            "Failed getting machine credentials: {reason}: {details}".format(
                reason=e.reason, details=e.read().decode("utf8")
            )
        )
    creds = json.loads(response.read().decode("utf8"))
    if creds is None:
        raise ExitError(
            "Failed getting machine credentials: Credentials not found"
        )
    creds["endpoint"] = maas_url + "/metadata/status/" + system_id
    return creds


def write_token(credentials, path=None):
    """Write the OAuth token for a machine.

    If a path is not provided, the yaml is printed out.
    """
    content = yaml.dump(
        {"reporting": {"maas": credentials}},
        default_flow_style=False,
    )
    if path:
        path.write_text(content)
    else:
        print(content)


def action_report_results(ns):
    config = get_config(ns)
    if not config.metadata_url:
        raise ExitError("No MAAS URL set")

    with TemporaryDirectory() as base_path:
        paths = ScriptsPaths(Path(base_path))
        paths.ensure()

        maas_url = get_base_url(config.metadata_url)
        metadata_url = maas_url + "/MAAS/metadata/" + MD_VERSION + "/"

        print(
            "* Fetching scripts from {url} to {dir}".format(
                url=metadata_url, dir=paths.scripts
            )
        )

        for script in fetch_scripts(
            maas_url, metadata_url, paths, config.credentials
        ):
            if not script.should_run():
                continue
            print(
                f"* Running '{script.name}'...",
                end="\n" if ns.debug else " ",
            )
            result = script.run(console_output=ns.debug)
            if ns.debug:
                print(
                    f"* Finished running '{script.name}': ",
                    end=" ",
                )
            if result.exit_status == 0:
                print("success")
            else:
                print(
                    "FAILED (status {result.exit_status}): {result.error}".format(
                        result=result
                    )
                )
            signal(
                metadata_url,
                config.credentials,
                result.status,
                error=result.error,
                script_name=script.name,
                script_result_id=script.info.get("script_result_id"),
                files=result.result_files,
                runtime=result.runtime,
                exit_status=result.exit_status,
                script_version_id=script.info.get("script_version_id"),
            )


def action_register_machine(ns):
    hostname = ns.hostname
    if not hostname:
        hostname = platform.node().split(".")[0]

    maas_url = ns.maas_url.rstrip("/")
    data, headers = encode_multipart_data(
        {
            b"hostname": hostname.encode("utf8"),
            b"deployed": b"true",
        }
    )
    try:
        response = geturl(
            maas_url + "/api/2.0/machines/",
            data=data,
            headers=headers,
            credentials=ns.admin_token,
            retry=False,
        )
    except urllib.error.HTTPError as e:
        raise ExitError(
            "Machine creation failed: {reason}: {details}".format(
                reason=e.reason, details=e.read().decode("utf8")
            )
        )
    result = json.loads(response.read().decode("utf8"))
    system_id = result["system_id"]
    print(
        "Machine {hostname} created with system ID: {system_id}".format(
            hostname=hostname,
            system_id=system_id,
        )
    )

    creds = get_machine_token(maas_url, ns.admin_token, system_id)
    creds_path = Path(ns.base_dir) / (hostname + "-creds.yaml")
    write_token(creds, path=creds_path)
    print(f"Machine token written to {creds_path}")


def action_get_machine_token(ns):
    maas_url = ns.maas_url.rstrip("/")
    creds = get_machine_token(maas_url, ns.admin_token, ns.system_id)
    path = Path(ns.token_file.name) if ns.token_file.seekable() else None
    write_token(creds, path=path)


ACTIONS = {
    "get-machine-token": action_get_machine_token,
    "register-machine": action_register_machine,
    "report-results": action_report_results,
}


def main(args):
    ns = parse_args(args)
    action = ACTIONS[ns.action]
    try:
        return action(ns)
    except ExitError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main(sys.argv[1:])
