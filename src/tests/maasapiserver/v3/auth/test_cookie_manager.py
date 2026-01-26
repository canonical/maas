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
            request, encryptor=encryptor, response=response, ttl_seconds=1200
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
            request, encryptor=encryptor, response=response, ttl_seconds=1200
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
            request, encryptor=encryptor, response=response, ttl_seconds=1200
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
            request, encryptor=Mock(), response=response, ttl_seconds=1200
        )

        result = manager.get_cookie("missing_key")

        request.cookies.get.assert_called_once_with("missing_key")
        assert result is None

    def test_clear_cookie(self) -> None:
        request = Mock()
        response = Mock()

        manager = EncryptedCookieManager(
            request, encryptor=Mock(), response=response, ttl_seconds=1200
        )

        result = manager.clear_cookie("some_key")

        response.set_cookie.assert_called_once_with(
            key="some_key", value="", max_age=0, expires=0
        )
        assert result is None

    def test_set_unsafe_cookie(self) -> None:
        request = Mock()
        response = Mock()
        encryptor = Mock()
        manager = EncryptedCookieManager(
            request, encryptor=encryptor, response=response, ttl_seconds=1200
        )

        manager.set_unsafe_cookie(key="key", value="value", path="/")

        response.set_cookie.assert_called_once_with(
            key="key", value="value", path="/"
        )

    def test_get_unsafe_cookie(self) -> None:
        request = Mock()
        response = Mock()
        request.cookies.get.return_value = "value"
        manager = EncryptedCookieManager(
            request, encryptor=Mock(), response=response, ttl_seconds=1200
        )

        result = manager.get_unsafe_cookie(key="key")

        request.cookies.get.assert_called_once_with("key")
        assert result == "value"

    def test_set_cookie_queues_when_no_response(self) -> None:
        request = Mock()
        encryptor = Mock()
        encryptor.encrypt.return_value = "encrypted_value"
        manager = EncryptedCookieManager(
            request, encryptor=encryptor, response=None, ttl_seconds=1200
        )

        manager.set_cookie(key="key", value="value", path="/")

        assert manager._pending == [("key", "encrypted_value", {"path": "/"})]

    def test_bind_response_sets_pending_cookies(self) -> None:
        request = Mock()
        response = Mock()
        encryptor = Mock()
        manager = EncryptedCookieManager(
            request, encryptor=encryptor, response=None, ttl_seconds=1200
        )
        manager._pending = [
            ("key1", "value1", {"path": "/"}),
            ("key2", "value2", {"httponly": True}),
        ]

        manager.bind_response(response=response)

        response.set_cookie.assert_any_call(
            key="key1", value="value1", path="/"
        )
        response.set_cookie.assert_any_call(
            key="key2", value="value2", httponly=True
        )
        assert manager._pending == []
        assert response.set_cookie.call_count == 2
