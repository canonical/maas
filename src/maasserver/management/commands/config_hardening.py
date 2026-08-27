# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
"""Django management command: config-hardening."""

from socket import AF_INET, AF_INET6

from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS

from maascommon.fips import is_fips_enabled
from maascommon.hardening import configure_hardening, is_hardening_enabled
from maasserver.config import RegionConfiguration
from maasserver.management.commands.base import BaseCommandWithConnection
from maasservicelayer.services.hardening import (
    _AUTO_DERIVED_BIND_KEYS,
    configure_and_validate_hardening,
)
from provisioningserver.utils.snap import running_in_snap

_CONFIG_KEYS = frozenset({"hardening_enabled", "fips_enabled"})

_CONF_KEYS = frozenset(
    {
        "api_tls_dhparam",
        "api_bind",
        "api_bind6",
        "prometheus_bind",
        "temporal_bind",
        "rpc_bind",
        "internal_api_bind",
        "internal_api_bind6",
        "dns_bind",
        "dns_bind6",
        "syslog_bind",
        "http_proxy_bind",
        "http_proxy_bind6",
        "database_sslmode",
        "database_sslcert",
        "database_sslkey",
        "database_sslrootcert",
    }
)

# Seeded to loopback by `enable`;
# network-facing binds are not auto-seeded.
_LOOPBACK_SEED_KEYS = frozenset({"prometheus_bind"})

# Keys backed by a comma-separated list in regiond.conf (see
# `ForEach` in `maasserver.config`). Every other conf-backed key is a
# plain scalar string.
_LIST_KEYS = frozenset(
    {
        "api_bind",
        "api_bind6",
        "rpc_bind",
        "internal_api_bind",
        "internal_api_bind6",
        "dns_bind",
        "dns_bind6",
        "syslog_bind",
        "http_proxy_bind",
        "http_proxy_bind6",
    }
)

# Only meaningful in snap deployments: MAAS owns the whole named.conf
# there. On Debian-packaged installs MAAS does not own the base
# named.conf.options, so these keys are refused entirely.
_SNAP_ONLY_KEYS = frozenset({"dns_bind", "dns_bind6"})

# Family to derive for keys resolved via `resolve_bind_addresses`
# (list-valued, per-family binds). Keys absent here (`rpc_bind`,
# `temporal_bind`, `syslog_bind`, `prometheus_bind`) are single mixed-family
# binds resolved differently -- see `_effective_bind_value`.
_BIND_FAMILY_FOR_KEY = {
    "api_bind": AF_INET,
    "api_bind6": AF_INET6,
    "internal_api_bind": AF_INET,
    "internal_api_bind6": AF_INET6,
    "http_proxy_bind": AF_INET,
    "http_proxy_bind6": AF_INET6,
}


def _effective_bind_value(
    key: str, maas_url: str, hardening_active: bool
) -> str:
    """Return what MAAS would actually bind `key` to right now, if unset.

    Mirrors the resolution each consuming service performs at startup (see
    `_AUTO_DERIVED_BIND_KEYS` in `maasservicelayer.services.hardening`).
    Returns "" when nothing more specific than "all interfaces" would
    result -- i.e. there is nothing useful to show.
    """
    from provisioningserver.utils.network import (
        resolve_bind_address,
        resolve_bind_addresses,
    )

    if key == "rpc_bind":
        from maasserver.eventloop import resolve_rpc_bind_addresses

        return ",".join(resolve_rpc_bind_addresses())
    if key == "temporal_bind":
        address = resolve_bind_address(
            "", maas_url, hardening_active=hardening_active
        )
        return "" if address in ("0.0.0.0", "::") else address
    if key == "syslog_bind":
        return ",".join(
            resolve_bind_addresses(
                [], maas_url, hardening_active=hardening_active
            )
        )
    if key == "prometheus_bind":
        return "127.0.0.1" if hardening_active else ""
    family = _BIND_FAMILY_FOR_KEY.get(key)
    if family is None:
        return ""
    return ",".join(
        resolve_bind_addresses(
            [], maas_url, hardening_active=hardening_active, family=family
        )
    )


_ALL_KNOWN_KEYS = _CONFIG_KEYS | _CONF_KEYS


def _is_conf_only_operation(command: str, key: str) -> bool:
    """True when the operation only touches regiond.conf (no DB needed)."""
    return command in ("set", "get") and _store_for(key) == "conf"


_HARDENING_ENABLED_VALUES = frozenset({"auto", "on", "off"})
_FIPS_ENABLED_TRUE = frozenset({"true", "on", "1", "yes"})
_FIPS_ENABLED_FALSE = frozenset({"false", "off", "0", "no"})


def _format_conf_value(key: str, value) -> str:
    if key in _LIST_KEYS:
        return ",".join(value)
    return str(value)


def _parse_conf_value(key: str, value: str):
    if key in _LIST_KEYS:
        return [addr.strip() for addr in value.split(",") if addr.strip()]
    return value


def _sanitize_hardening_enabled(value: str) -> str:
    canonical = value.strip().lower()
    if canonical not in _HARDENING_ENABLED_VALUES:
        raise ValueError(
            f"Invalid hardening_enabled value '{value}'."
            f" Must be one of: {sorted(_HARDENING_ENABLED_VALUES)}"
        )
    return canonical


def _sanitize_fips_enabled(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in _FIPS_ENABLED_TRUE:
        return True
    if lowered in _FIPS_ENABLED_FALSE:
        return False
    raise ValueError(
        f"Invalid fips_enabled value '{value}'."
        f" Use: on/off, true/false, yes/no, or 1/0"
    )


def _store_for(key: str) -> str:
    if key in _CONFIG_KEYS:
        return "config"
    if key in _CONF_KEYS:
        return "conf"
    return "unknown"


class Command(BaseCommandWithConnection):
    help = "Manage MAAS hardening configuration parameters."

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest="command")
        subparsers.required = True

        set_parser = subparsers.add_parser(
            "set", help="Set a hardening parameter."
        )
        set_parser.add_argument("key", help="Parameter name.")
        set_parser.add_argument("value", help="Parameter value.")

        get_parser = subparsers.add_parser(
            "get", help="Get a hardening parameter value."
        )
        get_parser.add_argument("key", help="Parameter name.")

        subparsers.add_parser("list", help="List all hardening parameters.")
        subparsers.add_parser(
            "validate",
            help="Run hardening validation; print violations; exit non-zero if any exist.",
        )
        subparsers.add_parser(
            "enable",
            help="Enable hardening and seed loopback defaults for unset region-internal binds.",
        )
        subparsers.add_parser(
            "disable",
            help="Disable hardening; refused on FIPS hosts.",
        )

    def execute(self, *args, **options):
        if _is_conf_only_operation(
            options.get("command", ""), options.get("key", "")
        ):
            options.setdefault("force_color", False)
            options.setdefault("no_color", False)
            options.setdefault("skip_checks", True)
            return BaseCommand.execute(self, *args, **options)
        return super().execute(*args, **options)

    def handle(self, *args, **options):
        command = options["command"]

        if _is_conf_only_operation(command, options.get("key", "")):
            if command == "set":
                self._cmd_set(options["key"], options["value"])
            elif command == "get":
                self._cmd_get(options["key"])
            return

        from maasserver.models.config import read_hardening_enabled_from_db

        configure_hardening(read_hardening_enabled_from_db())

        if command == "set":
            self._cmd_set(options["key"], options["value"])
        elif command == "get":
            self._cmd_get(options["key"])
        elif command == "list":
            self._cmd_list()
        elif command == "validate":
            self._cmd_validate()
        elif command == "enable":
            self._cmd_enable()
        elif command == "disable":
            self._cmd_disable()

    def _refuse_if_snap_only(self, key: str) -> None:
        if key in _SNAP_ONLY_KEYS and not running_in_snap():
            self.stderr.write(f"'{key}' is only available on snap installs.\n")
            raise SystemExit(1)

    def _cmd_set(self, key: str, value: str) -> None:
        self._refuse_if_snap_only(key)

        if key not in _ALL_KNOWN_KEYS:
            self.stderr.write(
                f"Unknown hardening key '{key}'."
                f" Known keys: {sorted(_ALL_KNOWN_KEYS)}\n"
                "To configure TLS certificate and key, use: maas config-tls enable\n"
            )
            raise SystemExit(1)

        if _store_for(key) == "conf":
            self._write_conf_key(key, value)
            self.stdout.write(f"Set {key} in regiond.conf\n")
            return

        try:
            if key == "hardening_enabled":
                stored = _sanitize_hardening_enabled(value)
            else:
                stored = _sanitize_fips_enabled(value)
        except ValueError as exc:
            self.stderr.write(f"{exc}\n")
            raise SystemExit(1) from exc

        from maasserver.models import Config

        Config.objects.db_manager(DEFAULT_DB_ALIAS).set_config(key, stored)
        self.stdout.write(f"Set {key} in DB Config store\n")

    def _cmd_get(self, key: str) -> None:
        self._refuse_if_snap_only(key)
        self.stdout.write(
            f"{key} [{_store_for(key)}] = {self._read_key(key)}\n"
        )

    def _cmd_list(self) -> None:
        conf_values = self._read_conf_values()
        hardening_active = is_hardening_enabled()
        maas_url = self._read_maas_url()

        try:
            from maasserver.certificates import get_maas_certificate

            tls = get_maas_certificate()
            tls_status = (
                "<configured>" if tls is not None else "<not configured>"
            )
        except Exception:
            tls_status = "<unknown>"
        self.stdout.write(
            f"{'tls_certificate/key':<35} [secret ] {tls_status}"
            " (manage with: maas config-tls enable)\n"
        )

        for key in sorted(_ALL_KNOWN_KEYS):
            if key in _SNAP_ONLY_KEYS and not running_in_snap():
                continue
            store = _store_for(key)
            value = (
                conf_values.get(key, "<not in conf>")
                if store == "conf"
                else self._read_key(key)
            )
            line = f"{key:<35} [{store:<7}] {value}"
            if not value and key in _AUTO_DERIVED_BIND_KEYS:
                effective = _effective_bind_value(
                    key, maas_url, hardening_active
                )
                if effective:
                    line += f"  (effective: {effective})"
            self.stdout.write(line + "\n")

    def _cmd_validate(self) -> None:
        if not is_hardening_enabled():
            self.stdout.write("Hardening is not active; no checks run.\n")
            return

        try:
            fips_declared = self._read_fips_declared()
        except Exception:
            fips_declared = None

        try:
            from maasserver.certificates import get_maas_certificate

            tls = get_maas_certificate()
            cert_pem = tls.certificate_pem().encode() if tls else None
            key_pem = tls.private_key_pem().encode() if tls else None
        except Exception:
            cert_pem = None
            key_pem = None

        try:
            with RegionConfiguration.open() as cfg:
                violations = configure_and_validate_hardening(
                    api_tls_cert_pem=cert_pem,
                    api_tls_key_pem=key_pem,
                    api_tls_dhparam=str(cfg.api_tls_dhparam),
                    api_bind=list(cfg.api_bind),
                    api_bind6=list(cfg.api_bind6),
                    prometheus_bind=str(cfg.prometheus_bind),
                    temporal_bind=str(cfg.temporal_bind),
                    rpc_bind=list(cfg.rpc_bind),
                    internal_api_bind=list(cfg.internal_api_bind),
                    internal_api_bind6=list(cfg.internal_api_bind6),
                    dns_bind=list(cfg.dns_bind),
                    dns_bind6=list(cfg.dns_bind6),
                    syslog_bind=list(cfg.syslog_bind),
                    http_proxy_bind=list(cfg.http_proxy_bind),
                    http_proxy_bind6=list(cfg.http_proxy_bind6),
                    database_sslmode=str(cfg.database_sslmode),
                    fips_declared=fips_declared,
                    snap_deployment=running_in_snap(),
                )
        except Exception as exc:
            self.stderr.write(f"Could not read configuration: {exc}\n")
            raise SystemExit(2) from exc

        if not violations:
            self.stdout.write("OK: no hardening violations.\n")
            return

        self.stdout.write(f"VIOLATIONS ({len(violations)}):\n")
        for v in violations:
            self.stdout.write(
                f"  [{v.code}] {v.message}\n"
                f"    Resolution: {v.resolution}\n"
                f"    Config key: {v.config_key}"
                + (f"  File: {v.file_path}" if v.file_path else "")
                + "\n"
            )
        raise SystemExit(1)

    def _cmd_enable(self) -> None:
        from maasserver.models import Config

        Config.objects.db_manager(DEFAULT_DB_ALIAS).set_config(
            "hardening_enabled", "on"
        )
        self.stdout.write("Hardening enabled (hardening_enabled=on).\n")

        seeded = []
        try:
            with RegionConfiguration.open_for_update() as cfg:
                for key in sorted(_LOOPBACK_SEED_KEYS):
                    if not str(getattr(cfg, key, "")):
                        setattr(cfg, key, "127.0.0.1")
                        seeded.append(key)
        except Exception as exc:
            self.stderr.write(
                f"Warning: could not seed bind defaults in regiond.conf: {exc}\n"
            )
            return

        if seeded:
            self.stdout.write(
                f"Seeded loopback (127.0.0.1) for: {', '.join(seeded)}\n"
            )
        else:
            self.stdout.write(
                "All region-internal bind keys already set; no seeding done.\n"
            )

    def _cmd_disable(self) -> None:
        if is_fips_enabled():
            self.stderr.write(
                "Cannot disable hardening on a FIPS-enabled host. "
                "Hardening is mandatory when FIPS mode is active.\n"
            )
            raise SystemExit(1)

        from maasserver.models import Config

        Config.objects.db_manager(DEFAULT_DB_ALIAS).set_config(
            "hardening_enabled", "off"
        )
        self.stdout.write("Hardening disabled (hardening_enabled=off).\n")

    def _write_conf_key(self, key: str, value: str) -> None:
        try:
            with RegionConfiguration.open_for_update() as cfg:
                setattr(cfg, key, _parse_conf_value(key, value))
        except Exception as exc:
            self.stderr.write(
                f"Could not write '{key}' to regiond.conf: {exc}\n"
            )
            raise SystemExit(2) from exc

    def _read_conf_values(self) -> dict:
        try:
            with RegionConfiguration.open() as cfg:
                return {
                    key: _format_conf_value(key, getattr(cfg, key))
                    for key in _CONF_KEYS
                }
        except Exception:
            return {}

    def _read_maas_url(self) -> str:
        try:
            with RegionConfiguration.open() as cfg:
                return str(cfg.maas_url)
        except Exception:
            return ""

    def _read_fips_declared(self) -> "bool | None":
        from maasserver.models import Config

        return Config.objects.db_manager(DEFAULT_DB_ALIAS).get_config(
            "fips_enabled"
        )

    def _read_key(self, key: str) -> str:
        store = _store_for(key)
        if store == "unknown":
            return "<unknown key>"
        if store == "config":
            from maasserver.models import Config

            value = Config.objects.db_manager(DEFAULT_DB_ALIAS).get_config(key)
            return str(value) if value is not None else "<not set>"
        return self._read_conf_values().get(key, "<not in conf>")
