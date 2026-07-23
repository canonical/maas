# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
"""Tests for the config-hardening management command."""

from io import StringIO
from unittest.mock import MagicMock, patch

from django.test import TestCase

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

    def test_set_conf_key_exits_with_error(self):
        with self.assertRaises(SystemExit) as ctx:
            self._cmd(command="set", key="api_bind", value="10.0.0.1")
        self.assertEqual(1, ctx.exception.code)

    def test_set_unknown_key_exits_with_error(self):
        with self.assertRaises(SystemExit) as ctx:
            self._cmd(command="set", key="nonexistent_key", value="val")
        self.assertEqual(1, ctx.exception.code)


class TestConfigHardeningValidate(_Base):
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
                return_value=MagicMock()
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
                    return_value=MagicMock()
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
    def _mock_region_cfg(self, MockRegionCfg, **attrs):
        mock_cfg = MagicMock(**attrs)
        MockRegionCfg.open_for_update.return_value.__enter__ = MagicMock(
            return_value=mock_cfg
        )
        MockRegionCfg.open_for_update.return_value.__exit__ = MagicMock(
            return_value=False
        )
        return mock_cfg

    def test_sets_config_and_seeds_unset_binds(self):
        with (
            patch("maasserver.models.Config") as MockConfig,
            patch(
                "maasserver.management.commands.config_hardening.RegionConfiguration"
            ) as MockRegionCfg,
        ):
            mock_mgr = MagicMock()
            MockConfig.objects.db_manager.return_value = mock_mgr
            mock_cfg = self._mock_region_cfg(
                MockRegionCfg, prometheus_bind="", temporal_bind=""
            )
            self._cmd(command="enable")

        self.assertEqual("127.0.0.1", mock_cfg.prometheus_bind)
        self.assertEqual("127.0.0.1", mock_cfg.temporal_bind)

    def test_skips_seeding_when_binds_already_set(self):
        with (
            patch("maasserver.models.Config"),
            patch(
                "maasserver.management.commands.config_hardening.RegionConfiguration"
            ) as MockRegionCfg,
        ):
            self._mock_region_cfg(
                MockRegionCfg,
                prometheus_bind="10.0.0.1",
                temporal_bind="10.0.0.2",
            )
            cmd = self._cmd(command="enable")
        self.assertIn("already set", cmd.stdout.getvalue())

    def test_warns_on_conf_write_failure(self):
        with (
            patch("maasserver.models.Config") as MockConfig,
            patch(
                "maasserver.management.commands.config_hardening.RegionConfiguration"
            ) as MockRegionCfg,
        ):
            mock_mgr = MagicMock()
            MockConfig.objects.db_manager.return_value = mock_mgr
            MockRegionCfg.open_for_update.side_effect = OSError("no file")
            cmd = self._cmd(command="enable")

        self.assertIn("Warning", cmd.stderr.getvalue())
        mock_mgr.set_config.assert_called_once_with("hardening_enabled", "on")
