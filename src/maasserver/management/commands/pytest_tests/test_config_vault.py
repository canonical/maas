from unittest.mock import MagicMock

from django.core.management import CommandError
import pytest
import yaml

from maasserver.management.commands import config_vault
from maasserver.management.commands.config_vault import Command
from maasserver.models import (
    Config,
    ControllerInfo,
    RegionControllerProcess,
    Secret,
)
from maasserver.secrets import GLOBAL_SECRETS, SecretManager
from maasserver.testing.factory import factory
from maasserver.testing.vault import FakeVaultClient
from maasserver.vault import VaultError, WrappedSecretError
from provisioningserver.utils.env import MAAS_ID


@pytest.fixture
def configure_mock(mocker):
    mocker.patch.object(Command, "_set_vault_configured_db_flag")
    yield mocker.patch.object(config_vault, "configure_region_with_vault")


@pytest.mark.usefixtures("maasdb")
class TestConfigVaultConfigurateCommand:
    def _configure_kwargs(
        self,
        role_id: str = factory.make_UUID(),
        wrapped_token: str = factory.make_UUID(),
        secrets_path: str = "path",
        mount: str = "secrets",
        yes: bool = True,
    ) -> dict:
        return {
            "command": Command.CONFIGURE_COMMAND,
            "url": "http://vault:8200",
            "role_id": role_id,
            "wrapped_token": wrapped_token,
            "secrets_path": secrets_path,
            "mount": mount,
            "yes": yes,
        }

    def test_success(self, configure_mock):
        kwargs = self._configure_kwargs()
        result = Command().handle(**kwargs)
        configure_mock.assert_called_once_with(
            url=kwargs["url"],
            role_id=kwargs["role_id"],
            wrapped_token=kwargs["wrapped_token"],
            secrets_path=kwargs["secrets_path"],
            secrets_mount=kwargs["mount"],
        )
        assert "sudo maas config-vault migrate" in result

    def test_wraps_specific_exceptions_only(self, configure_mock):
        handler = Command()
        side_effects = [VaultError("error"), WrappedSecretError()]
        configure_mock.side_effect = side_effects
        kwargs = self._configure_kwargs()

        for _ in side_effects:
            with pytest.raises(CommandError):
                handler.handle(**kwargs)

        unexpected = factory.make_exception()
        configure_mock.side_effect = [unexpected]
        with pytest.raises(type(unexpected)):
            handler.handle(**kwargs)

    def test_will_not_prompt_with_no_existing_config(
        self, mocker, configure_mock
    ):
        get_client_mock = mocker.patch.object(
            config_vault, "get_region_vault_client"
        )
        get_client_mock.return_value = None
        prompt_mock = mocker.patch.object(config_vault, "prompt_yes_no")

        Command().handle(**self._configure_kwargs(yes=False))
        prompt_mock.assert_not_called()

    def test_will_prompt_with_existing_config(self, mocker, configure_mock):
        get_client_mock = mocker.patch.object(
            config_vault, "get_region_vault_client"
        )
        get_client_mock.return_value = "Not None"
        prompt_mock = mocker.patch.object(config_vault, "prompt_yes_no")

        Command().handle(**self._configure_kwargs(yes=False))
        prompt_mock.assert_called_once()

    def test_will_not_prompt_with_ignore_existing(
        self, mocker, configure_mock
    ):
        get_client_mock = mocker.patch.object(
            config_vault, "get_region_vault_client"
        )
        get_client_mock.return_value = "Not None"
        prompt_mock = mocker.patch.object(config_vault, "prompt_yes_no")

        Command().handle(**self._configure_kwargs(yes=True))
        prompt_mock.assert_not_called()

    def test_handle_will_remove_trailing_slashes(self, mocker):
        handler = Command()
        handler_configure_mock = mocker.patch.object(
            handler, "_configure_vault"
        )
        expected = "trailing/slash/test"
        kwargs = self._configure_kwargs(
            secrets_path=f"{expected}/////", mount=f"{expected}/"
        )
        handler.handle(**kwargs)
        handler_configure_mock.assert_called_once_with(
            kwargs["url"],
            kwargs["role_id"],
            kwargs["wrapped_token"],
            expected,
            kwargs["yes"],
            expected,
        )


@pytest.mark.usefixtures("maasdb")
class TestSetVaultConfiguredDbCommand:
    def test_does_nothing_when_no_maas_id(self):
        assert MAAS_ID.get() is None
        assert not Command()._set_vault_configured_db_flag()

    def test_does_nothing_when_region_controller_not_found(self):
        MAAS_ID.set(factory.make_UUID())
        assert not Command()._set_vault_configured_db_flag()

    def test_sets_flag(self, mocker):
        node = factory.make_RegionController()
        MAAS_ID.set(factory.make_UUID())
        mocker.patch.object(
            config_vault.RegionController.objects, "get_running_controller"
        ).return_value = node
        ci, created = ControllerInfo.objects.update_or_create(node=node)
        assert created
        assert not ci.vault_configured

        Command()._set_vault_configured_db_flag()
        assert ControllerInfo.objects.get(node_id=node.id).vault_configured


@pytest.mark.usefixtures("maasdb")
class TestConfigVaultMigrateCommand:
    def test_raises_when_vault_already_enabled(self):
        Config.objects.set_config("vault_enabled", True)
        with pytest.raises(
            CommandError, match="Secrets are already migrated to Vault"
        ):
            Command().handle(command=Command.MIGRATE_COMMAND)

    def test_raises_when_vault_not_configured_locally(self, mocker):
        mocker.patch.object(
            config_vault, "get_region_vault_client"
        ).return_value = None
        get_client_mock = mocker.patch.object(
            config_vault, "get_region_vault_client"
        )
        get_client_mock.return_value = None
        with pytest.raises(
            CommandError,
            match="Vault is not configured for the current region",
        ):
            Command().handle(command=Command.MIGRATE_COMMAND)

    def test_raises_when_vault_not_configured_somewhere(self, mocker):
        mocker.patch.object(
            config_vault, "get_region_vault_client"
        ).return_value = MagicMock()
        node = factory.make_RegionController()
        ci, _ = ControllerInfo.objects.update_or_create(node=node)
        assert not ci.vault_configured
        with pytest.raises(
            CommandError,
            match=f"Vault is not configured for regions: {node.hostname}",
        ):
            Command().handle(command=Command.MIGRATE_COMMAND)

    def test_calls_restart_and_migrate_secrets(self, mocker):
        target = Command()
        client = MagicMock()
        mocker.patch.object(
            config_vault, "get_region_vault_client"
        ).return_value = client
        restart_mock = mocker.patch.object(target, "_restart_regions")
        migrate_mock = mocker.patch.object(target, "_migrate_secrets")
        target.handle(command=Command.MIGRATE_COMMAND)
        restart_mock.assert_called_once()
        migrate_mock.assert_called_once_with(client)


@pytest.mark.usefixtures("maasdb")
class TestMigrateSecrets:
    def test_migrate_secrets_enables_vault(self, mocker):
        assert not Config.objects.get_config("vault_enabled", False)
        mocker.patch.object(config_vault, "notify")
        Command()._migrate_secrets(MagicMock())
        assert Config.objects.get_config("vault_enabled", False)

    def test_migrate_secrets_actually_migrates_secrets(self):
        client = FakeVaultClient()
        secrets = []
        for path in GLOBAL_SECRETS:
            value = factory.make_name("value")
            Secret(path=f"global/{path}", value=value).save()
            secrets.append((path, value))

        Command()._migrate_secrets(client)
        secret_manager = SecretManager(client)
        for path, value in secrets:
            assert value == secret_manager.get_composite_secret(path)
        assert not Secret.objects.exists()

    def test_handle_migrate_stops_when_vault_is_enabled(self, mocker):
        get_vault_mock = mocker.patch.object(
            config_vault, "get_region_vault_client"
        )
        Config.objects.set_config("vault_enabled", True)
        with pytest.raises(CommandError, match="already migrated"):
            Command()._handle_migrate({})
        get_vault_mock.assert_not_called()

    def test_handle_migrate_stops_when_no_client(self, mocker):
        mocker.patch.object(
            config_vault, "get_region_vault_client"
        ).return_value = None
        with pytest.raises(
            CommandError, match="Vault is not configured for the current"
        ):
            Command()._handle_migrate({})

    def test_handle_migrate_stops_when_regions_unconfigured(self, mocker):
        mocker.patch.object(
            config_vault, "get_region_vault_client"
        ).return_value = MagicMock()
        region_one = factory.make_RegionController()
        region_two = factory.make_RegionController()
        ControllerInfo(node=region_one, vault_configured=True).save()
        ControllerInfo(node=region_two, vault_configured=False).save()
        with pytest.raises(
            CommandError, match="Vault is not configured for regions"
        ):
            Command()._handle_migrate({})

    def test_handle_migrate_success(self, mocker):
        restart_mock = mocker.patch.object(Command, "_restart_regions")
        migrate_mock = mocker.patch.object(Command, "_migrate_secrets")
        client = MagicMock()
        mocker.patch.object(
            config_vault, "get_region_vault_client"
        ).return_value = client
        observed = Command()._handle_migrate({})
        client.check_authentication.assert_called_once()
        restart_mock.assert_called_once()
        migrate_mock.assert_called_once_with(client)
        assert observed == "Successfully migrated cluster secrets to Vault"

    def test_handle_migrate_raises_when_client_check_fails(self, mocker):
        client = MagicMock()
        mocker.patch.object(
            config_vault, "get_region_vault_client"
        ).return_value = client
        expected_error = factory.make_name("error")

        def error(*args, **kwargs):
            try:
                raise Exception(expected_error)
            except Exception as e:
                raise VaultError(e) from e

        client.check_authentication = error
        with pytest.raises(CommandError, match=expected_error):
            Command()._handle_migrate({})

    def test_get_online_regions_returns_correct_online_status(self):
        running = factory.make_RegionController(hostname="running")
        factory.make_RegionController(hostname="stopped")
        for j in range(2):
            RegionControllerProcess(region=running, pid=j).save()

        observed = Command()._get_online_regions()
        assert observed == ["running"]

    def test_restart_regions_wont_retry_with_no_active_regions(self, mocker):
        target = Command()
        online_regions_mock = mocker.patch.object(
            target, "_get_online_regions"
        )
        online_regions_mock.return_value = []
        notify_mock = mocker.patch.object(config_vault, "notify")
        sleep_mock = mocker.patch.object(config_vault.time, "sleep")
        target._restart_regions()
        online_regions_mock.assert_called_once()
        notify_mock.assert_called_once()
        sleep_mock.assert_called_once()

    def test_restart_regions_will_notify_once(self, mocker):
        target = Command()
        online_regions_mock = mocker.patch.object(
            target, "_get_online_regions"
        )
        online_regions_mock.side_effect = [
            ["test"],
            ["test"],
            [],
        ]
        notify_mock = mocker.patch.object(config_vault, "notify")
        sleep_mock = mocker.patch.object(config_vault.time, "sleep")
        target._restart_regions()
        notify_mock.assert_called_once()
        assert (
            sleep_mock.call_count == 3
        )  # One sleep at the start, two in the loop

    def test_restart_regions_will_raise_when_attempts_exhausted(self, mocker):
        target = Command()
        online_regions_mock = mocker.patch.object(
            target, "_get_online_regions"
        )
        online_regions_mock.return_value = {"test": True}
        notify_mock = mocker.patch.object(config_vault, "notify")
        mocker.patch.object(config_vault.time, "sleep")
        with pytest.raises(CommandError, match="Unable to migrate"):
            target._restart_regions()
        assert notify_mock.call_count == 1


@pytest.mark.usefixtures("maasdb")
class TestStatus:
    def test_status_not_enabled(self, capsys):
        region_one = factory.make_RegionController(hostname="one")
        region_two = factory.make_RegionController(hostname="two")
        ControllerInfo(node=region_one, vault_configured=True).save()
        ControllerInfo(node=region_two, vault_configured=False).save()
        Command()._handle_status({})
        assert yaml.safe_load(capsys.readouterr().out) == {
            "status": "disabled",
            "unconfigured_regions": ["two"],
        }

    def test_status_enabled(self, capsys):
        region_one = factory.make_RegionController(hostname="one")
        region_two = factory.make_RegionController(hostname="two")
        ControllerInfo(node=region_one, vault_configured=True).save()
        ControllerInfo(node=region_two, vault_configured=True).save()
        Config.objects.set_config("vault_enabled", True)
        Command()._handle_status({})
        assert yaml.safe_load(capsys.readouterr().out) == {"status": "enabled"}
