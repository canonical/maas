from unittest.mock import Mock

from maasapiserver.v3.auth.cookie_manager import (
    EncryptedCookieManager,
    MAAS_NONCE_COOKIE_NAME,
    MAAS_STATE_COOKIE_NAME,
    MAASOAuth2Cookie,
)


class TestCookieManager:
    def test_set_state_cookie(
        self,
    ) -> None:
        request = Mock()
        response = Mock()
        encryptor = Mock()
        set_cookie = Mock()
        manager = EncryptedCookieManager(
            request, response, encryptor=encryptor, ttl_seconds=1200
        )
        manager.set_cookie = set_cookie

        manager.set_auth_cookie(
            value="state_value", key=MAASOAuth2Cookie.AUTH_STATE
        )

        set_cookie.assert_called_once_with(
            key=MAAS_STATE_COOKIE_NAME,
            value="state_value",
            max_age=1200,
            httponly=True,
            secure=True,
        )

    def test_set_nonce_cookie(
        self,
    ) -> None:
        request = Mock()
        response = Mock()
        encryptor = Mock()
        set_cookie = Mock()
        manager = EncryptedCookieManager(
            request, response, encryptor=encryptor, ttl_seconds=1200
        )
        manager.set_cookie = set_cookie

        manager.set_auth_cookie(
            value="nonce_value", key=MAASOAuth2Cookie.AUTH_NONCE
        )

        set_cookie.assert_called_once_with(
            key=MAAS_NONCE_COOKIE_NAME,
            value="nonce_value",
            max_age=1200,
            httponly=True,
            secure=True,
        )

    def test_get_cookie_returns_value(
        self,
    ) -> None:
        request = Mock()
        response = Mock()
        encryptor = Mock()
        request.cookies.get.return_value = "encrypted_cookie_value"
        encryptor.decrypt.return_value = "cookie_value"
        manager = EncryptedCookieManager(
            request, response, encryptor=encryptor, ttl_seconds=1200
        )

        result = manager.get_cookie("some_key")

        request.cookies.get.assert_called_once_with("some_key")
        assert result == "cookie_value"

    def test_get_cookie_returns_none_when_cookie_missing(
        self,
    ) -> None:
        request = Mock()
        request.cookies.get.return_value = None
        response = Mock()

        manager = EncryptedCookieManager(
            request, response, encryptor=Mock(), ttl_seconds=1200
        )

        result = manager.get_cookie("missing_key")

        request.cookies.get.assert_called_once_with("missing_key")
        assert result is None

    def test_clear_cookie(self) -> None:
        request = Mock()
        response = Mock()

        manager = EncryptedCookieManager(
            request, response, encryptor=Mock(), ttl_seconds=1200
        )

        result = manager.clear_cookie("some_key")

        response.delete_cookie.assert_called_once_with(key="some_key")
        assert result is None
