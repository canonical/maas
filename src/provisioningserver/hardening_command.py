# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""``maas-rack config-hardening``: manage rack-side hardening configuration.

Mirrors ``maas config-hardening`` on the region (see
`maasserver.management.commands.config_hardening`), scoped to the keys the
rack controller owns in `rackd.conf` (`ClusterConfiguration`). The rack has
no database: every hardening key here is conf-backed, and `validate` checks
only the bind-wildcard rules that apply locally -- TLS certificate, DH
parameter, and database sslmode checks are region-only concerns.
"""

import argparse

from maascommon.hardening import (
    check_bind_violations,
    configure_hardening,
    is_hardening_enabled,
)
from provisioningserver.config import ClusterConfiguration
from provisioningserver.utils.snap import running_in_snap

_COMMAND_PREFIX = "maas-rack config-hardening"

_HARDENING_ENABLED_VALUES = frozenset({"auto", "on", "off"})

# Keys backed by a comma-separated list in rackd.conf (`ForEach` in
# `provisioningserver.config.ClusterConfiguration`). `rpc_bind` is a plain
# scalar string there, unlike its region counterpart.
_LIST_KEYS = frozenset(
    {
        "api_bind",
        "api_bind6",
        "dns_bind",
        "dns_bind6",
        "syslog_bind",
        "http_proxy_bind",
        "http_proxy_bind6",
    }
)

_BIND_KEYS = _LIST_KEYS | frozenset({"rpc_bind"})

_ALL_KEYS = _BIND_KEYS | frozenset({"hardening_enabled"})

# Keys whose empty value derives a specific, non-wildcard address from
# maas_url at rack startup (see `rackdservices/http.py`, `dns/config.py`,
# and their tests). `rpc_bind` and `dns_bind`/`dns_bind6` have no such
# derivation: an unset `rpc_bind` really does bind all interfaces, and DNS
# must be explicitly picked to serve every managed subnet.
_AUTO_DERIVED_BIND_KEYS = frozenset(
    {
        "api_bind",
        "api_bind6",
        "syslog_bind",
        "http_proxy_bind",
        "http_proxy_bind6",
    }
)

# Only meaningful in snap deployments: MAAS owns the whole named.conf
# there. On Debian-packaged installs MAAS does not own the base
# named.conf.options, so these keys are refused entirely.
_SNAP_ONLY_KEYS = frozenset({"dns_bind", "dns_bind6"})


def _format_value(key: str, value) -> str:
    if key in _LIST_KEYS:
        return ",".join(value)
    return str(value)


def _parse_value(key: str, value: str):
    if key in _LIST_KEYS:
        return [addr.strip() for addr in value.split(",") if addr.strip()]
    return value


def _sanitize_hardening_enabled(value: str) -> str:
    canonical = value.strip().lower()
    if canonical not in _HARDENING_ENABLED_VALUES:
        raise argparse.ArgumentTypeError(
            "hardening_enabled must be one of "
            f"{sorted(_HARDENING_ENABLED_VALUES)}, got {value!r}"
        )
    return canonical


def add_arguments(parser):
    """Add this command's options to the `ArgumentParser`."""
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    subparsers.add_parser("list", help="List all rack hardening parameters.")

    get_parser = subparsers.add_parser(
        "get", help="Get a rack hardening parameter value."
    )
    get_parser.add_argument("key", choices=sorted(_ALL_KEYS))

    set_parser = subparsers.add_parser(
        "set", help="Set a rack hardening parameter value."
    )
    set_parser.add_argument("key", choices=sorted(_ALL_KEYS))
    set_parser.add_argument("value")

    subparsers.add_parser(
        "validate",
        help=(
            "Run hardening validation against rackd.conf; print "
            "violations; exit non-zero if any exist."
        ),
    )


def _cmd_list():
    with ClusterConfiguration.open() as config:
        for key in sorted(_ALL_KEYS):
            if key in _SNAP_ONLY_KEYS and not running_in_snap():
                continue
            value = getattr(config, key)
            print(f"{key:<20} {_format_value(key, value)}")


def _cmd_get(key: str):
    if key in _SNAP_ONLY_KEYS and not running_in_snap():
        raise SystemExit(
            f"{key} is only available on snap deployments (MAAS does not "
            "own named.conf.options on Debian-packaged installs)."
        )
    with ClusterConfiguration.open() as config:
        print(_format_value(key, getattr(config, key)))


def _cmd_set(key: str, value: str):
    if key in _SNAP_ONLY_KEYS and not running_in_snap():
        raise SystemExit(
            f"{key} is only available on snap deployments (MAAS does not "
            "own named.conf.options on Debian-packaged installs)."
        )
    parsed = (
        _sanitize_hardening_enabled(value)
        if key == "hardening_enabled"
        else _parse_value(key, value)
    )
    with ClusterConfiguration.open_for_update() as config:
        setattr(config, key, parsed)
    print(f"{key} set.")


def _cmd_validate():
    with ClusterConfiguration.open() as config:
        hardening_enabled = str(config.hardening_enabled)
        binds = {
            key: getattr(config, key)
            for key in _BIND_KEYS
            if key not in _SNAP_ONLY_KEYS or running_in_snap()
        }

    configure_hardening(hardening_enabled)
    hardening_active = is_hardening_enabled()

    if not hardening_active:
        print("Hardening is not active on this rack controller.")
        return

    normalized = {
        key: (value if isinstance(value, list) else ([value] if value else []))
        for key, value in binds.items()
    }
    violations = check_bind_violations(
        normalized, _AUTO_DERIVED_BIND_KEYS, _COMMAND_PREFIX
    )

    if not violations:
        print("OK: no hardening violations.")
        return

    print(f"VIOLATIONS ({len(violations)}):")
    for v in violations:
        print(f"  [{v.code}] {v.message}")
        print(f"    Resolution: {v.resolution}")
        print(f"    Config key: {v.config_key}")
    raise SystemExit(1)


def run(args):
    """Manage rack hardening configuration parameters."""
    if args.command == "list":
        _cmd_list()
    elif args.command == "get":
        _cmd_get(args.key)
    elif args.command == "set":
        _cmd_set(args.key, args.value)
    elif args.command == "validate":
        _cmd_validate()
