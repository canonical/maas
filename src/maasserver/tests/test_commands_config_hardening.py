# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
"""Tests for the config-hardening management command."""

from io import StringIO
from unittest.mock import MagicMock, patch

from django.test import TestCase

from maasserver.management.commands.base import BaseCommandWithConnection
from maasserver.management.commands.config_hardening import Command

_PATCH_CONFIGURE = patch(
    "maasserver.management.commands.config_hardening.configure_hardening"
)


class _Base(TestCase):
    def setUp(self):
        super().setUp()
        _PATCH_CONFIGURE.start()
        self.addCleanup(_PATCH_CONFIGURE.stop)

    def _cmd(self, **kw):
        cmd = Command(stdout=StringIO(), stderr=StringIO())
        cmd.handle(**kw)
        return cmd


class TestConfigHardeningSet(_Base):
    def test_set_config_key_writes_to_db(self):
        with patch("maasserver.models.Config") as MockConfig:
            mock_mgr = MagicMock()
            MockConfig.objects.db_manager.return_value = mock_mgr
            self._cmd(command="set", key="hardening_enabled", value="on")
        mock_mgr.set_config.assert_called_once_with("hardening_enabled", "on")

    def test_set_conf_key_writes_to_regiond_conf(self):
        with patch(
            "maasserver.management.commands.config_hardening.RegionConfiguration"
        ) as MockRegionCfg:
            mock_cfg = MagicMock()
            MockRegionCfg.open_for_update.return_value.__enter__ = MagicMock(
                return_value=mock_cfg
            )
            MockRegionCfg.open_for_update.return_value.__exit__ = MagicMock(
                return_value=False
            )
            cmd = self._cmd(
                command="set", key="database_sslmode", value="prefer"
            )
        self.assertEqual("prefer", mock_cfg.database_sslmode)
        self.assertIn("database_sslmode", cmd.stdout.getvalue())

    def test_set_conf_key_works_without_db(self):
        with (
            patch(
                "maasserver.utils.orm.with_connection",
                side_effect=Exception("DB connection refused"),
            ),
            patch(
                "maasserver.management.commands.config_hardening.RegionConfiguration"
            ) as MockRegionCfg,
        ):
            mock_cfg = MagicMock()
            MockRegionCfg.open_for_update.return_value.__enter__ = MagicMock(
                return_value=mock_cfg
            )
            MockRegionCfg.open_for_update.return_value.__exit__ = MagicMock(
                return_value=False
            )
            cmd = Command(stdout=StringIO(), stderr=StringIO())
            cmd.execute(command="set", key="database_sslmode", value="prefer")
        self.assertIn("database_sslmode", cmd.stdout.getvalue())

    def test_set_config_key_requires_db_connection(self):
        with patch.object(
            BaseCommandWithConnection, "execute", autospec=True
        ) as mock_execute:
            mock_execute.return_value = None
            cmd = Command(stdout=StringIO(), stderr=StringIO())
            cmd.execute(command="set", key="hardening_enabled", value="on")
        mock_execute.assert_called_once()

    def test_set_unknown_key_exits_with_error(self):
        with self.assertRaises(SystemExit) as ctx:
            self._cmd(command="set", key="nonexistent_key", value="val")
        self.assertEqual(1, ctx.exception.code)


class TestConfigHardeningSnapOnlyKeys(_Base):
    def test_set_dns_bind_refused_outside_snap(self):
        with patch(
            "maasserver.management.commands.config_hardening.running_in_snap",
            return_value=False,
        ):
            with self.assertRaises(SystemExit) as ctx:
                self._cmd(command="set", key="dns_bind", value="10.0.0.1")
        self.assertEqual(1, ctx.exception.code)

    def test_set_dns_bind6_refused_outside_snap(self):
        with patch(
            "maasserver.management.commands.config_hardening.running_in_snap",
            return_value=False,
        ):
            with self.assertRaises(SystemExit) as ctx:
                self._cmd(command="set", key="dns_bind6", value="fd00::1")
        self.assertEqual(1, ctx.exception.code)

    def test_set_dns_bind_allowed_in_snap(self):
        with (
            patch(
                "maasserver.management.commands.config_hardening.running_in_snap",
                return_value=True,
            ),
            patch(
                "maasserver.management.commands.config_hardening.RegionConfiguration"
            ) as MockRegionCfg,
        ):
            mock_cfg = MagicMock()
            MockRegionCfg.open_for_update.return_value.__enter__ = MagicMock(
                return_value=mock_cfg
            )
            MockRegionCfg.open_for_update.return_value.__exit__ = MagicMock(
                return_value=False
            )
            self._cmd(command="set", key="dns_bind", value="10.0.0.1")
        self.assertEqual(["10.0.0.1"], mock_cfg.dns_bind)

    def test_get_dns_bind_refused_outside_snap(self):
        with patch(
            "maasserver.management.commands.config_hardening.running_in_snap",
            return_value=False,
        ):
            with self.assertRaises(SystemExit) as ctx:
                self._cmd(command="get", key="dns_bind")
        self.assertEqual(1, ctx.exception.code)

    def test_list_excludes_dns_bind_outside_snap(self):
        with (
            patch(
                "maasserver.management.commands.config_hardening.running_in_snap",
                return_value=False,
            ),
            patch(
                "maasserver.management.commands.config_hardening.RegionConfiguration"
            ) as MockRegionCfg,
            patch("maasserver.models.Config") as MockConfig,
        ):
            mock_cfg = MagicMock()
            MockRegionCfg.open.return_value.__enter__ = MagicMock(
                return_value=mock_cfg
            )
            MockRegionCfg.open.return_value.__exit__ = MagicMock(
                return_value=False
            )
            MockConfig.objects.db_manager.return_value.get_config.return_value = None
            cmd = self._cmd(command="list")
        self.assertNotIn("dns_bind ", cmd.stdout.getvalue())
        self.assertNotIn("dns_bind6", cmd.stdout.getvalue())

    def test_list_includes_dns_bind_in_snap(self):
        with (
            patch(
                "maasserver.management.commands.config_hardening.running_in_snap",
                return_value=True,
            ),
            patch(
                "maasserver.management.commands.config_hardening.RegionConfiguration"
            ) as MockRegionCfg,
            patch(
                "maasserver.certificates.get_maas_certificate",
                return_value=None,
            ),
            patch("maasserver.models.Config") as MockConfig,
        ):
            mock_cfg = MagicMock()
            MockRegionCfg.open.return_value.__enter__ = MagicMock(
                return_value=mock_cfg
            )
            MockRegionCfg.open.return_value.__exit__ = MagicMock(
                return_value=False
            )
            MockConfig.objects.db_manager.return_value.get_config.return_value = None
            cmd = self._cmd(command="list")
        self.assertIn("dns_bind6", cmd.stdout.getvalue())


class TestConfigHardeningGet(_Base):
    def test_get_conf_key_reads_from_regiond_conf(self):
        with patch(
            "maasserver.management.commands.config_hardening.RegionConfiguration"
        ) as MockRegionCfg:
            mock_cfg = MagicMock()
            mock_cfg.api_bind = ["10.0.0.1"]
            mock_cfg.api_bind6 = []
            mock_cfg.api_tls_dhparam = ""
            mock_cfg.prometheus_bind = "127.0.0.1"
            mock_cfg.temporal_bind = "127.0.0.1"
            mock_cfg.rpc_bind = ["127.0.0.1"]
            mock_cfg.dns_bind = []
            mock_cfg.dns_bind6 = []
            mock_cfg.database_sslmode = "prefer"
            mock_cfg.database_sslcert = ""
            mock_cfg.database_sslkey = ""
            mock_cfg.database_sslrootcert = ""
            MockRegionCfg.open.return_value.__enter__ = MagicMock(
                return_value=mock_cfg
            )
            MockRegionCfg.open.return_value.__exit__ = MagicMock(
                return_value=False
            )
            cmd = self._cmd(command="get", key="api_bind")
        self.assertIn("10.0.0.1", cmd.stdout.getvalue())

    def test_get_conf_key_works_without_db(self):
        with (
            patch(
                "maasserver.utils.orm.with_connection",
                side_effect=Exception("DB connection refused"),
            ),
            patch(
                "maasserver.management.commands.config_hardening.RegionConfiguration"
            ) as MockRegionCfg,
        ):
            mock_cfg = MagicMock()
            mock_cfg.prometheus_bind = "127.0.0.1"
            mock_cfg.api_bind = []
            mock_cfg.api_bind6 = []
            mock_cfg.api_tls_dhparam = ""
            mock_cfg.temporal_bind = ""
            mock_cfg.rpc_bind = []
            mock_cfg.dns_bind = []
            mock_cfg.dns_bind6 = []
            mock_cfg.database_sslmode = ""
            mock_cfg.database_sslcert = ""
            mock_cfg.database_sslkey = ""
            mock_cfg.database_sslrootcert = ""
            MockRegionCfg.open.return_value.__enter__ = MagicMock(
                return_value=mock_cfg
            )
            MockRegionCfg.open.return_value.__exit__ = MagicMock(
                return_value=False
            )
            cmd = Command(stdout=StringIO(), stderr=StringIO())
            cmd.execute(command="get", key="prometheus_bind")
        self.assertIn("127.0.0.1", cmd.stdout.getvalue())

    def test_get_config_key_requires_db_connection(self):
        with patch.object(
            BaseCommandWithConnection, "execute", autospec=True
        ) as mock_execute:
            mock_execute.return_value = None
            cmd = Command(stdout=StringIO(), stderr=StringIO())
            cmd.execute(command="get", key="hardening_enabled")
        mock_execute.assert_called_once()


class TestConfigHardeningValidate(_Base):
    @staticmethod
    def _mock_cfg():
        return MagicMock(
            api_tls_dhparam="",
            api_bind=[],
            api_bind6=[],
            prometheus_bind="",
            temporal_bind="",
            rpc_bind=[],
            dns_bind=[],
            dns_bind6=[],
            database_sslmode="",
        )

    def _run_validate(self, violations, hardening_active=True):
        with (
            patch(
                "maasserver.management.commands.config_hardening"
                ".is_hardening_enabled",
                return_value=hardening_active,
            ),
            patch(
                "maasserver.management.commands.config_hardening"
                ".configure_and_validate_hardening",
                return_value=violations,
            ),
            patch(
                "maasserver.management.commands.config_hardening.RegionConfiguration"
            ) as MockCfg,
        ):
            MockCfg.open.return_value.__enter__ = MagicMock(
                return_value=self._mock_cfg()
            )
            MockCfg.open.return_value.__exit__ = MagicMock(return_value=False)
            return self._cmd(command="validate")

    def test_no_violations_exits_zero(self):
        cmd = self._run_validate([])
        self.assertIn("OK", cmd.stdout.getvalue())

    def test_violations_exit_nonzero(self):
        from maasservicelayer.services.hardening import (
            _ident,
            HardeningViolation,
        )

        v = HardeningViolation(
            ident=_ident("MISSING_TLS_CERT"),
            code="MISSING_TLS_CERT",
            message="cert missing",
            resolution="fix it",
            config_key="api_tls_cert",
        )
        with self.assertRaises(SystemExit) as ctx:
            self._run_validate([v])
        self.assertEqual(1, ctx.exception.code)

    def test_hardening_inactive_skips_checks(self):
        cmd = self._run_validate([], hardening_active=False)
        self.assertIn("not active", cmd.stdout.getvalue())

    def test_fips_host_enables_hardening_automatically(self):
        """On a FIPS host with hardening_enabled=auto, validate must run checks."""
        import maascommon.hardening as _h

        _PATCH_CONFIGURE.stop()
        orig = (_h._hardening_active, _h._hardening_configured)
        _h._hardening_active = False
        _h._hardening_configured = False
        try:
            with (
                patch(
                    "maascommon.hardening.is_fips_enabled", return_value=True
                ),
                patch(
                    "maasserver.management.commands.config_hardening"
                    ".configure_and_validate_hardening",
                    return_value=[],
                ),
                patch(
                    "maasserver.management.commands.config_hardening.RegionConfiguration"
                ) as MockCfg,
            ):
                MockCfg.open.return_value.__enter__ = MagicMock(
                    return_value=self._mock_cfg()
                )
                MockCfg.open.return_value.__exit__ = MagicMock(
                    return_value=False
                )
                cmd = self._cmd(command="validate")
            self.assertNotIn("not active", cmd.stdout.getvalue())
        finally:
            _h._hardening_active, _h._hardening_configured = orig
            _PATCH_CONFIGURE.start()


class TestConfigHardeningDisable(_Base):
    def test_refused_on_fips_host(self):
        with patch(
            "maasserver.management.commands.config_hardening.is_fips_enabled",
            return_value=True,
        ):
            cmd = Command(stdout=StringIO(), stderr=StringIO())
            with self.assertRaises(SystemExit) as ctx:
                cmd.handle(command="disable")
        self.assertEqual(1, ctx.exception.code)
        self.assertIn("FIPS", cmd.stderr.getvalue())

    def test_sets_config_on_non_fips(self):
        with (
            patch(
                "maasserver.management.commands.config_hardening.is_fips_enabled",
                return_value=False,
            ),
            patch("maasserver.models.Config") as MockConfig,
        ):
            mock_mgr = MagicMock()
            MockConfig.objects.db_manager.return_value = mock_mgr
            self._cmd(command="disable")
        mock_mgr.set_config.assert_called_once_with("hardening_enabled", "off")


class TestConfigHardeningEnable(_Base):
    def test_sets_hardening_enabled_in_db(self):
        with patch("maasserver.models.Config") as MockConfig:
            mock_mgr = MagicMock()
            MockConfig.objects.db_manager.return_value = mock_mgr
            cmd = self._cmd(command="enable")

        mock_mgr.set_config.assert_called_once_with("hardening_enabled", "on")
        self.assertIn("Hardening enabled", cmd.stdout.getvalue())

    def test_enable_does_not_touch_regiond_conf(self):
        # `enable` is a pure DB operation; it must never open regiond.conf
        # (it used to seed a prometheus_bind loopback default there).
        with (
            patch("maasserver.models.Config"),
            patch(
                "maasserver.management.commands.config_hardening.RegionConfiguration"
            ) as MockRegionCfg,
        ):
            self._cmd(command="enable")

        MockRegionCfg.open_for_update.assert_not_called()
        MockRegionCfg.open.assert_not_called()


class TestConfigHardeningListEffectiveBinds(_Base):
    @staticmethod
    def _mock_cfg(**overrides):
        defaults = dict(
            api_tls_dhparam="",
            api_bind=[],
            api_bind6=[],
            prometheus_bind="",
            temporal_bind="",
            rpc_bind=[],
            agent_api_bind=[],
            agent_api_bind6=[],
            dns_bind=[],
            dns_bind6=[],
            syslog_bind=[],
            http_proxy_bind=[],
            http_proxy_bind6=[],
            database_sslmode="prefer",
            database_sslcert="",
            database_sslkey="",
            database_sslrootcert="",
            maas_url="http://10.0.0.9:5240/MAAS",
        )
        defaults.update(overrides)
        return MagicMock(**defaults)

    def _run_list(self, mock_cfg, hardening_active):
        with (
            patch(
                "maasserver.management.commands.config_hardening"
                ".is_hardening_enabled",
                return_value=hardening_active,
            ),
            patch(
                "maasserver.management.commands.config_hardening.RegionConfiguration"
            ) as MockRegionCfg,
            patch(
                "maasserver.certificates.get_maas_certificate",
                return_value=None,
            ),
            patch("maasserver.models.Config") as MockConfig,
        ):
            MockRegionCfg.open.return_value.__enter__ = MagicMock(
                return_value=mock_cfg
            )
            MockRegionCfg.open.return_value.__exit__ = MagicMock(
                return_value=False
            )
            MockConfig.objects.db_manager.return_value.get_config.return_value = None
            cmd = self._cmd(command="list")
        return cmd.stdout.getvalue()

    @staticmethod
    def _line_for(output, key):
        for line in output.splitlines():
            if line.split()[0] == key:
                return line
        raise AssertionError(f"no '{key}' line in output:\n{output}")

    def test_hardening_gated_binds_not_effective_when_hardening_inactive(
        self,
    ):
        # api_bind/http_proxy_bind/syslog_bind only derive under hardening;
        # rpc_bind/temporal_bind derive from maas_url regardless (see
        # `AUTO_DERIVED_BIND_KEYS`/`resolve_rpc_bind_addresses`), so they
        # are checked separately and excluded here.
        import provisioningserver.utils.network as network_module

        with patch.object(
            network_module,
            "get_source_address_for_url",
            return_value="10.0.0.9",
        ):
            output = self._run_list(self._mock_cfg(), hardening_active=False)
        for key in (
            "api_bind",
            "api_bind6",
            "agent_api_bind",
            "agent_api_bind6",
            "http_proxy_bind",
            "http_proxy_bind6",
            "syslog_bind",
        ):
            self.assertNotIn("effective", self._line_for(output, key))

    def test_api_bind_shows_effective_value_under_hardening(self):
        import provisioningserver.utils.network as network_module

        with patch.object(
            network_module,
            "get_source_address_for_url",
            return_value="10.0.0.9",
        ):
            output = self._run_list(self._mock_cfg(), hardening_active=True)
        self.assertIn(
            "(effective: 10.0.0.9)", self._line_for(output, "api_bind")
        )

    def test_explicit_bind_not_annotated_as_effective(self):
        import provisioningserver.utils.network as network_module

        with patch.object(
            network_module,
            "get_source_address_for_url",
            return_value="10.0.0.9",
        ):
            output = self._run_list(
                self._mock_cfg(api_bind=["10.0.0.5"]), hardening_active=True
            )
        self.assertNotIn("effective", self._line_for(output, "api_bind"))

    def test_rpc_bind_shows_effective_value_regardless_of_hardening(self):
        with patch(
            "maasserver.eventloop.resolve_rpc_bind_addresses",
            return_value=["10.0.0.9"],
        ):
            output = self._run_list(self._mock_cfg(), hardening_active=False)
        self.assertIn(
            "(effective: 10.0.0.9)", self._line_for(output, "rpc_bind")
        )

    def test_prometheus_bind_shows_loopback_effective_under_hardening(self):
        output = self._run_list(self._mock_cfg(), hardening_active=True)
        self.assertIn(
            "(effective: 127.0.0.1)",
            self._line_for(output, "prometheus_bind"),
        )

    def test_prometheus_bind_no_effective_value_outside_hardening(self):
        output = self._run_list(self._mock_cfg(), hardening_active=False)
        self.assertNotIn(
            "effective", self._line_for(output, "prometheus_bind")
        )
