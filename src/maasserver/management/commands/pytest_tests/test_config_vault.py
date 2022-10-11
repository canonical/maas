from django.core.management import CommandError
from hvac.exceptions import VaultError
import pytest
from requests.exceptions import ConnectionError

from maasserver.management.commands import config_vault
from maasserver.management.commands.config_vault import Command
from maasserver.vault import WrappedSecretError
from maastesting.factory import factory


@pytest.fixture
def configure_mock(mocker):
    yield mocker.patch.object(config_vault, "configure_region_with_vault")


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
        side_effects = [ConnectionError(), VaultError(), WrappedSecretError()]
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
