# Copyright 2017-2019 Canonical Ltd.  This software is licensed under the GNU
# Affero General Public License version 3 (see the file LICENSE).

"""Snap management commands."""

import argparse
from collections import OrderedDict
import grp
import os
from pathlib import Path
import pwd
import subprocess
import sys
from textwrap import dedent
import threading
import time

import netifaces
import psycopg2
from psycopg2.extensions import parse_dsn

from maascli.command import Command, CommandError
from maascli.configfile import MAASConfiguration
from maascli.init import (
    add_candid_options,
    add_create_admin_options,
    add_rbac_options,
    print_msg,
    prompt_for_choices,
    read_input,
)

ARGUMENTS = OrderedDict(
    [
        (
            "maas-url",
            {
                "help": (
                    "URL that MAAS should use for communicate from the nodes to "
                    "MAAS and other controllers of MAAS."
                ),
                "for_mode": ["region+rack", "region", "rack"],
            },
        ),
        (
            "database-uri",
            {
                "help": (
                    "URI for the MAAS Postgres database in the form of "
                    "postgres://user:pass@host:port/dbname or "
                    "maas-test-db:///. For maas-test-db:/// to work, the "
                    "maas-test-db snap needs to be installed and connected"
                ),
                "for_mode": ["region+rack", "region"],
            },
        ),
        (
            "vault-uri",
            {"help": "Vault URI", "for_mode": ["region+rack", "region"]},
        ),
        (
            "vault-approle-id",
            {
                "help": "Vault AppRole Role ID",
                "for_mode": ["region+rack", "region"],
            },
        ),
        (
            "vault-wrapped-token",
            {
                "help": "Vault Wrapped Token for AppRole ID",
                "for_mode": ["region+rack", "region"],
            },
        ),
        (
            "vault-secrets-path",
            {
                "help": "Path prefix for MAAS secrets in Vault KV storage",
                "for_mode": ["region+rack", "region"],
            },
        ),
        (
            "vault-secrets-mount",
            {
                "help": "Vault KV mount path",
                "for_mode": ["region+rack", "region"],
                "default": "secret",
            },
        ),
        (
            "secret",
            {
                "help": (
                    "Secret token required for the rack controller to talk "
                    "to the region controller(s). Only used when in 'rack' mode."
                ),
                "for_mode": ["rack"],
            },
        ),
        (
            "num-workers",
            {
                "type": int,
                "help": "Number of regiond worker processes to run.",
                "for_mode": ["region+rack", "region"],
            },
        ),
        (
            "enable-debug",
            {
                "action": "store_true",
                "help": (
                    "Enable debug mode for detailed error and log reporting."
                ),
                "for_mode": ["region+rack", "region"],
            },
        ),
        (
            "disable-debug",
            {
                "action": "store_true",
                "help": "Disable debug mode.",
                "for_mode": ["region+rack", "region"],
            },
        ),
        (
            "enable-debug-queries",
            {
                "action": "store_true",
                "help": (
                    "Enable query debugging. Reports number of queries and time for "
                    "all actions performed. Requires debug to also be True. mode for "
                    "detailed error and log reporting."
                ),
                "for_mode": ["region+rack", "region"],
            },
        ),
        (
            "disable-debug-queries",
            {
                "action": "store_true",
                "help": "Disable query debugging.",
                "for_mode": ["region+rack", "region"],
            },
        ),
    ]
)

NON_ROOT_USER = "snap_daemon"
PEBBLE_LAYER_BASE = "001-maas-base-layer.yaml"
PEBBLE_LAYER_REGION = "002-maas-region-layer.yaml"
PEBBLE_LAYER_RACK = "003-maas-rack-layer.yaml"


def get_default_gateway_ip():
    """Return the default gateway IP."""
    gateways = netifaces.gateways()
    defaults = gateways.get("default")
    if not defaults:
        return

    def default_ip(family):
        gw_info = defaults.get(family)
        if not gw_info:
            return
        addresses = netifaces.ifaddresses(gw_info[1]).get(family)
        if addresses:
            return addresses[0]["addr"]

    return default_ip(netifaces.AF_INET) or default_ip(netifaces.AF_INET6)


def get_default_url():
    """Return the best default URL for MAAS."""
    gateway_ip = get_default_gateway_ip()
    if not gateway_ip:
        gateway_ip = "localhost"
    return "http://%s:5240/MAAS" % gateway_ip


def get_mode_filepath():
    """Return the path to the 'snap_mode' file."""
    return os.path.join(os.environ["SNAP_COMMON"], "snap_mode")


def get_current_mode():
    """Gets the current mode of the snap."""
    filepath = get_mode_filepath()
    if os.path.exists(filepath):
        with open(get_mode_filepath()) as fp:
            return fp.read().strip()
    else:
        return "none"


def set_current_mode(mode):
    """Set the current mode of the snap."""
    with open(get_mode_filepath(), "w") as fp:
        fp.write(mode.strip())


def stop_pebble():
    subprocess.run(["snapctl", "stop", "maas.pebble"])


def restart_pebble(restart_inactive=False):
    """Cause pebble to stop all processes, reload configuration, and
    start all processes. Will not issue restart command when service
    is inactive and `restart_inactive` is False."""

    if not restart_inactive:
        status_call = subprocess.run(
            ["snapctl", "services", "maas"], capture_output=True
        )
        if b"inactive" in status_call.stdout:
            return

    subprocess.run(["snapctl", "restart", "maas.pebble"])


def print_config_value(config, key, hidden=False):
    """Print the configuration value to stdout."""
    template = "{key}=(hidden)" if hidden else "{key}={value}"
    print_msg(template.format(key=key, value=config.get(key)))


def _get_rpc_secret_path() -> Path:
    """Get the path for the shared secret file."""
    base_path = os.getenv("MAAS_DATA", "/var/lib/maas")
    return Path(base_path) / "secret"


def get_rpc_secret():
    """Get the current RPC secret."""
    secret = None
    secret_path = _get_rpc_secret_path()
    if secret_path.exists():
        secret = secret_path.read_text().strip()
    if secret:
        return secret


def set_rpc_secret(secret):
    """Write/delete the RPC secret."""
    secret_path = _get_rpc_secret_path()
    if secret:
        secret_path.write_text(secret)
    else:
        # Delete the secret.
        if secret_path.exists():
            secret_path.unlink()


def print_config(
    parsable=False, show_database_password=False, show_secret=False
):
    """Print the config output."""
    current_mode = get_current_mode()
    config = MAASConfiguration().get()
    if parsable:
        print_msg("mode=%s" % current_mode)
    else:
        print_msg("Mode: %s" % current_mode)
    if current_mode != "none":
        if not parsable:
            print_msg("Settings:")
        print_config_value(config, "maas_url")
        if "debug" in config:
            print_config_value(config, "debug")
        if current_mode in ["region+rack", "region"]:
            print_config_value(config, "database_host")
            print_config_value(config, "database_port")
            print_config_value(config, "database_name")
            print_config_value(config, "database_user")
            print_config_value(
                config, "database_pass", hidden=(not show_database_password)
            )
        if current_mode == "rack":
            secret = "(hidden)"
            if show_secret:
                secret = get_rpc_secret()
            print_msg("secret=%s" % secret)
        if current_mode != "rack":
            if "num_workers" in config:
                print_config_value(config, "num_workers")
            if "debug_queries" in config:
                print_config_value(config, "debug_queries")


def change_user(username, effective=False):
    """Change running user, by default to the non-root user."""
    running_uid = pwd.getpwnam(username).pw_uid
    running_gid = grp.getgrnam(username).gr_gid
    os.setgroups([])
    if effective:
        os.setegid(running_gid)
        os.seteuid(running_uid)
    else:
        os.setgid(running_gid)
        os.setuid(running_uid)


def db_need_init(connection=None) -> bool:
    """Whether the database needs initializing.

    It assumes the database is set up if there's any table in it.
    """
    if connection is None:
        # local import since the CLI shouldn't unconditionally depend on Django
        from django.db import connection

    try:
        return not connection.introspection.table_names()
    except Exception:
        return True


def migrate_db(capture=False):
    """Migrate the database."""
    if capture:
        process = subprocess.Popen(
            [
                os.path.join(os.environ["SNAP"], "bin", "maas-region"),
                "dbupgrade",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        ret = process.wait()
        output = process.stdout.read().decode("utf-8")
        if ret != 0:
            clear_line()
            print_msg("Failed to perfom migrations:")
            print_msg(output)
            print_msg("")
            sys.exit(ret)
    else:
        subprocess.check_call(
            [
                os.path.join(os.environ["SNAP"], "bin", "maas-region"),
                "dbupgrade",
            ]
        )


def clear_line():
    """Resets the current line when in a terminal."""
    if sys.stdout.isatty():
        print_msg(
            "\r" + " " * int(os.environ.get("COLUMNS", 0)), newline=False
        )


def perform_work(msg, cmd, *args, **kwargs):
    """Perform work.

    Executes the `cmd` and while its running it prints a nice message.
    """
    # When not running in a terminal, just print the message once and perform
    # the operation.
    if not sys.stdout.isatty():
        print_msg(msg)
        return cmd(*args, **kwargs)

    spinner = {
        0: "/",
        1: "-",
        2: "\\",
        3: "|",
        4: "/",
        5: "-",
        6: "\\",
        7: "|",
    }

    def _write_msg(evnt):
        idx = 0
        while not evnt.is_set():
            # Print the message with a spinner until the work is complete.
            print_msg(f"\r[{spinner[idx]}] {msg}", newline=False)
            idx += 1
            if idx == 8:
                idx = 0
            time.sleep(0.25)
        # Clear the line so previous message is not show if the next message
        # is not as long as this message.
        print_msg("\r" + " " * (len(msg) + 4), newline=False)

    # Spawn a thread to print the message, while performing the work in the
    # current execution thread.
    evnt = threading.Event()
    t = threading.Thread(target=_write_msg, args=(evnt,))
    t.start()
    try:
        ret = cmd(*args, **kwargs)
    finally:
        evnt.set()
        t.join()
    clear_line()
    return ret


def required_prompt(title, help_text=None, default=None):
    """Prompt for required input."""
    value = None
    if default is not None:
        default_text = f" [default={default}]"
    else:
        default_text = ""
    prompt = f"{title}{default_text}: "
    while not value or value == "help":
        value = read_input(prompt)
        if not value and default is not None:
            value = default

        if value == "help":
            if help_text:
                print_msg(help_text)
    return value


class SnapCommand(Command):
    """
    Command that just prints the exception instead of the overridden
    'maas --help' output.
    """

    def __call__(self, options):
        try:
            self.handle(options)
        except Exception as exc:
            exc.always_show = True
            raise exc


class DatabaseSettingsError(Exception):
    """Something was wrong with the database settings."""


MAAS_TEST_DB_URI = "maas-test-db:///"


def get_database_settings(options):
    """Get the database setting to use.

    It will either read --database-uri from the options, or prompt for it.
    When prompting for it, it will default to the maas-test-db URI if the
    maas-test-db snap is installed and connected.

    """
    database_uri = options.database_uri
    test_db_socket = os.path.join(os.environ["SNAP_COMMON"], "test-db-socket")
    test_db_uri = f"postgres:///maasdb?host={test_db_socket}&user=maas"
    if database_uri is None:
        default_uri = None
        if os.path.exists(test_db_socket):
            default_uri = MAAS_TEST_DB_URI
        database_uri = required_prompt(
            "Database URI",
            default=default_uri,
            help_text=ARGUMENTS["database-uri"]["help"],
        )
        if not database_uri:
            database_uri = test_db_uri
    # parse_dsn gives very confusing error messages if you pass in
    # an invalid URI, so let's make sure the URI is of the form
    # postgres://... before calling parse_dsn.
    if database_uri != MAAS_TEST_DB_URI and not database_uri.startswith(
        "postgres://"
    ):
        raise DatabaseSettingsError(
            f"Database URI needs to be either '{MAAS_TEST_DB_URI}' or "
            "start with 'postgres://'"
        )
    if database_uri == MAAS_TEST_DB_URI:
        database_uri = test_db_uri
    try:
        parsed_dsn = parse_dsn(database_uri)
    except psycopg2.ProgrammingError as error:
        raise DatabaseSettingsError(
            "Error parsing database URI: " + str(error).strip()
        )
    unsupported_params = set(parsed_dsn.keys()).difference(
        ["user", "password", "host", "dbname", "port"]
    )
    if unsupported_params:
        raise DatabaseSettingsError(
            "Error parsing database URI: Unsupported parameters: "
            + ", ".join(sorted(unsupported_params))
        )
    if "user" not in parsed_dsn:
        raise DatabaseSettingsError(f"No user found in URI: {database_uri}")
    if "host" not in parsed_dsn:
        parsed_dsn["host"] = "localhost"
    if "dbname" not in parsed_dsn:
        parsed_dsn["dbname"] = parsed_dsn["user"]
    database_settings = {
        "database_host": parsed_dsn["host"],
        "database_name": parsed_dsn["dbname"],
        "database_user": parsed_dsn.get("user", ""),
        "database_pass": parsed_dsn.get("password"),
    }
    if "port" in parsed_dsn:
        database_settings["database_port"] = int(parsed_dsn["port"])
    return database_settings


def get_vault_settings(options) -> dict:
    """Get vault settings dict to use.

    If `vault-uri` argument is not present, method returns empty dict.
    Otherwise, it will:
     - check if required Vault parameters were provided (and raise CommandException if not)
     - check if Vault is reachable
     - try to unwrap secret_id for the provided approle
     - check if provided approle has all the permissions required
     - return configuration parameters dict
    """
    if not options.vault_uri:
        return {}

    from maasserver.vault import prepare_wrapped_approle, VaultError

    required_arguments = [
        "vault-approle-id",
        "vault-wrapped-token",
        "vault-secrets-path",
    ]
    missing_arguments = [
        key
        for key in required_arguments
        if getattr(options, key.replace("-", "_"), None) is None
    ]
    if missing_arguments:
        raise CommandError(
            f"Missing required vault arguments: {', '.join(missing_arguments)}"
        )

    try:
        secret_id = prepare_wrapped_approle(
            url=options.vault_uri,
            role_id=options.vault_approle_id,
            wrapped_token=options.vault_wrapped_token,
            secrets_path=options.vault_secrets_path,
            secrets_mount=options.vault_secrets_mount,
        )
    except VaultError as e:
        raise CommandError(e)

    return {
        "vault_url": options.vault_uri,
        "vault_approle_id": options.vault_approle_id,
        "vault_secret_id": secret_id,
        "vault_secrets_mount": options.vault_secrets_mount,
        "vault_secrets_path": options.vault_secrets_path,
    }


class cmd_init(SnapCommand):
    """Initialise MAAS in the specified run mode.

    When installing region or rack+region modes, MAAS needs a
    PostgreSQL database to connect to.

    If you want to set up PostgreSQL for a non-production deployment on
    this machine, and configure it for use with MAAS, you can install
    the maas-test-db snap before running 'maas init':

        sudo snap install maas-test-db
        sudo maas init region+rack --database-uri maas-test-db:///

    """

    def __init__(self, parser):
        super().__init__(parser)
        subparsers = parser.add_subparsers(
            metavar=None, title="run modes", dest="run_mode"
        )
        subparsers.required = True
        subparsers_map = {}
        subparsers_map["region+rack"] = subparsers.add_parser(
            "region+rack",
            help="Both region and rack controllers",
            description=(
                "Initialise MAAS to run both a region and rack controller."
            ),
        )
        subparsers_map["region"] = subparsers.add_parser(
            "region",
            help="Region controller only",
            description=("Initialise MAAS to run only a region controller."),
        )
        subparsers_map["rack"] = subparsers.add_parser(
            "rack",
            help="Rack controller only",
            description=("Initialise MAAS to run only a rack controller."),
        )
        for argument, kwargs in ARGUMENTS.items():
            kwargs = kwargs.copy()
            for_modes = kwargs.pop("for_mode")
            for for_mode in for_modes:
                subparsers_map[for_mode].add_argument(
                    "--%s" % argument, **kwargs
                )

        for for_mode in ("region+rack", "region", "rack"):
            subparsers_map[for_mode].add_argument(
                "--force",
                action="store_true",
                help=(
                    "Skip confirmation questions when initialization has "
                    "already been performed."
                ),
            )
        for for_mode in ["region+rack", "region"]:
            add_candid_options(subparsers_map[for_mode], suppress_help=True)
            add_rbac_options(subparsers_map[for_mode], suppress_help=True)
            subparsers_map[for_mode].add_argument(
                "--skip-admin", action="store_true", help=argparse.SUPPRESS
            )
            add_create_admin_options(
                subparsers_map[for_mode], suppress_help=True
            )

    def handle(self, options):
        if os.getuid() != 0:
            raise SystemExit("The 'init' command must be run by root.")

        mode = options.run_mode
        current_mode = get_current_mode()
        if current_mode != "none":
            if not options.force:
                init_text = "initialize again"
                if mode == "none":
                    init_text = "de-initialize"
                else:
                    print_msg("Controller has already been initialized.")
                initialize = prompt_for_choices(
                    "Are you sure you want to %s "
                    "(yes/no) [default=no]? " % init_text,
                    ["yes", "no"],
                    default="no",
                )
                if initialize == "no":
                    sys.exit(0)

        rpc_secret = None
        vault_settings = {}
        if mode in ("region", "region+rack"):
            try:
                database_settings = get_database_settings(options)
            except DatabaseSettingsError as error:
                raise CommandError(str(error))

            vault_settings = get_vault_settings(options)
        else:
            database_settings = {}
        maas_url = options.maas_url
        if mode != "none" and not maas_url:
            maas_url = required_prompt(
                "MAAS URL",
                default=get_default_url(),
                help_text=ARGUMENTS["maas-url"]["help"],
            )
        if mode == "rack":
            rpc_secret = options.secret
            if not rpc_secret:
                rpc_secret = required_prompt(
                    "Secret", help_text=ARGUMENTS["secret"]["help"]
                )

        if current_mode != "none":
            perform_work("Stopping services", stop_pebble)

        # Configure the settings.
        settings = {"maas_url": maas_url}
        settings.update(database_settings)
        # Note: we store DB creds regardless of vault configuration, since
        # the cluster might have `vault_enabled=False` => no creds should be there yet.
        # Otherwise, if `vault_enabled` is `True` or this is a clean install,
        # DB credentials will be moved to Vault on the first start.
        settings.update(vault_settings)

        MAASConfiguration().update(settings)
        set_rpc_secret(rpc_secret)

        # Finalize the Initialization.
        self._finalize_init(mode)

    def _finalize_init(self, mode):
        # Configure mode.
        def start_services():
            set_current_mode(mode)
            # From UX perspective, it makes sense to start MAAS after
            # initialization even if it was stopped.
            restart_pebble(restart_inactive=True)

        init_db = mode in ("region", "region+rack") and db_need_init()
        if init_db:
            # When in 'region' or 'region+rack' the migrations for the database
            # must be at the same level as this controller.
            perform_work(
                "Performing database migrations",
                migrate_db,
                capture=sys.stdout.isatty(),
            )

        perform_work(
            "Starting services" if mode != "none" else "Stopping services",
            start_services,
        )
        if init_db:
            print_msg(
                dedent(
                    """\
                    MAAS has been set up.

                    If you want to configure external authentication or use
                    MAAS with Canonical RBAC, please run

                      sudo maas configauth

                    To create admins when not using external authentication, run

                      sudo maas createadmin

                    To enable TLS for secured communication, please run

                      sudo maas config-tls enable
                    """
                )
            )


class cmd_config(SnapCommand):
    """View or change controller configuration."""

    # Required options based on mode.
    required_options = {
        "region+rack": [
            "maas_url",
            "database_host",
            "database_name",
            "database_user",
            "database_pass",
        ],
        "region": [
            "maas_url",
            "database_host",
            "database_name",
            "database_user",
            "database_pass",
        ],
        "rack": ["maas_url", "secret"],
        "none": [],
    }

    # Required flags that are in .conf.
    setting_flags = ("maas_url",)

    # Optional flags that are in .conf.
    optional_flags = {
        "num_workers": {"type": "int", "config": "num_workers"},
        "enable_debug": {
            "type": "store_true",
            "set_value": True,
            "config": "debug",
        },
        "disable_debug": {
            "type": "store_true",
            "set_value": False,
            "config": "debug",
        },
        "enable_debug_queries": {
            "type": "store_true",
            "set_value": True,
            "config": "debug_queries",
        },
        "disable_debug_queries": {
            "type": "store_true",
            "set_value": False,
            "config": "debug_queries",
        },
    }

    def __init__(self, parser):
        super().__init__(parser)
        parser.add_argument(
            "--show",
            action="store_true",
            help=(
                "Show the current configuration. Default when no parameters "
                "are provided."
            ),
        )
        parser.add_argument(
            "--show-database-password",
            action="store_true",
            help="Show the hidden database password.",
        )
        parser.add_argument(
            "--show-secret",
            action="store_true",
            help="Show the hidden secret.",
        )
        for argument, kwargs in ARGUMENTS.items():
            if argument == "database-uri":
                # 'maas config' doesn't support database-uri, since it's
                # more of a low-level tool for changing the MAAS
                # configuration directly.
                continue
            kwargs = kwargs.copy()
            kwargs.pop("for_mode")
            parser.add_argument("--%s" % argument, **kwargs)
        parser.add_argument(
            "--parsable",
            action="store_true",
            help="Output the current configuration in a parsable format.",
        )

    def _validate_flags(self, options, running_mode):
        """
        Validate the flags are correct for the current mode or the new mode.
        """
        invalid_flags = []
        for flag in self.setting_flags + ("secret",):
            if flag not in self.required_options[running_mode] and getattr(
                options, flag
            ):
                invalid_flags.append("--%s" % flag.replace("_", "-"))
        if len(invalid_flags) > 0:
            print_msg(
                "Following flags are not supported in '%s' mode: %s"
                % (running_mode, ", ".join(invalid_flags))
            )
            sys.exit(1)

    def handle(self, options):
        if os.getuid() != 0:
            raise SystemExit("The 'config' command must be run by root.")

        config_manager = MAASConfiguration()

        # In config mode if --show is passed or none of the following flags
        # have been passed.
        in_config_mode = options.show
        if not in_config_mode:
            in_config_mode = not any(
                (
                    getattr(options, flag) is not None
                    and getattr(options, flag) is not False
                )
                for flag in (
                    ("secret",)
                    + self.setting_flags
                    + tuple(self.optional_flags.keys())
                )
            )

        # Config mode returns the current config of the snap.
        if in_config_mode:
            return print_config(
                options.parsable,
                options.show_database_password,
                options.show_secret,
            )
        else:
            restart_required = False
            running_mode = get_current_mode()

            # Validate the mode and flags.
            self._validate_flags(options, running_mode)

            current_config = config_manager.get()
            # Only update the passed settings.
            for flag in self.setting_flags:
                flag_value = getattr(options, flag)
                should_update = (
                    flag_value is not None
                    and current_config.get(flag) != flag_value
                )
                if should_update:
                    config_manager.update({flag: flag_value})
                    restart_required = True
            if options.secret is not None:
                set_rpc_secret(options.secret)

            # fetch config again, as it might have changed
            current_config = config_manager.get()

            # Update any optional settings.
            for flag, flag_info in self.optional_flags.items():
                flag_value = getattr(options, flag)
                if flag_info["type"] != "store_true":
                    flag_key = flag_info["config"]
                    should_update = (
                        flag_value is not None
                        and current_config.get(flag_key) != flag_value
                    )
                    if should_update:
                        config_manager.update({flag_key: flag_value})
                        restart_required = True
                elif flag_value:
                    flag_key = flag_info["config"]
                    flag_value = flag_info["set_value"]
                    if current_config.get(flag_key) != flag_value:
                        config_manager.update({flag_key: flag_value})
                        restart_required = True

            # Restart the pebble as its required.
            if restart_required:
                perform_work(
                    (
                        "Restarting services"
                        if running_mode != "none"
                        else "Stopping services"
                    ),
                    restart_pebble,
                )


class cmd_status(SnapCommand):
    """Status of controller services."""

    def handle(self, options):
        if os.getuid() != 0:
            raise SystemExit("The 'status' command must be run by root.")

        if get_current_mode() == "none":
            print_msg("MAAS is not configured")
            sys.exit(1)
        else:
            process = subprocess.Popen(
                [
                    os.path.join(os.environ["SNAP"], "bin", "run-pebble"),
                    "services",
                ],
                stdout=subprocess.PIPE,
            )
            ret = process.wait()
            output = process.stdout.read().decode("utf-8")
            if ret == 0:
                print_msg(output, newline=False)
            else:
                print_msg(
                    f"Pebble exited with error code {ret} "
                    "and the following output:"
                )
                print_msg(output, newline=False)
                sys.exit(ret)


class cmd_migrate(SnapCommand):
    """Perform migrations on connected database."""

    def __init__(self, parser):
        super().__init__(parser)
        # '--configure' is hidden and only called from snap hooks to update the
        # database when running in "all" mode
        parser.add_argument(
            "--configure", action="store_true", help=argparse.SUPPRESS
        )

    def handle(self, options):
        if os.getuid() != 0:
            raise SystemExit("The 'migrate' command must be run by root.")

        current_mode = get_current_mode()
        # Hidden parameter that is only called from the configure hook. Updates
        # the database when running in all mode.
        if options.configure:
            if current_mode in ["region", "region+rack"]:
                sys.exit(migrate_db())
            else:
                # In 'rack' or 'none' mode, nothing to do.
                sys.exit(0)

        if current_mode == "none":
            print_msg("MAAS is not configured")
            sys.exit(1)
        elif current_mode == "rack":
            print_msg(
                "Mode 'rack' is not connected to a database. "
                "No migrations to perform."
            )
            sys.exit(1)
        else:
            sys.exit(migrate_db())
