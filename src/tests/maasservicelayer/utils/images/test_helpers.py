# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import MagicMock, patch

import pytest
from simplestreams.util import SignatureMissingException

from maasservicelayer.utils.images.helpers import (
    get_os_from_product,
    get_signing_policy,
)
from maastesting.factory import factory


class TestGetSigningPolicy:
    def test_picks_nonchecking_policy_for_json_index(self) -> None:
        path = "streams/v1/index.json"
        policy = get_signing_policy(path)
        content = factory.make_string()

        assert content == policy(content, path, factory.make_name("keyring"))

    def test_picks_checking_policy_for_sjson_index(self) -> None:
        path = "streams/v1/index.sjson"
        content = factory.make_string()
        policy = get_signing_policy(path)

        with pytest.raises(SignatureMissingException):
            policy(content, path, factory.make_name("keyring"))

    def test_picks_checking_policy_for_json_gpg_index(self) -> None:
        path = "streams/v1/index.json.gpg"
        content = factory.make_string()
        policy = get_signing_policy(path)

        with pytest.raises(SignatureMissingException):
            policy(content, path, factory.make_name("keyring"))

    @patch("maasservicelayer.utils.images.helpers.policy_read_signed")
    def test_injects_default_keyring_if_passed(
        self,
        mock_policy_read_signed: MagicMock,
    ) -> None:
        path = "streams/v1/index.json.gpg"
        content = factory.make_string()
        keyring = factory.make_name("keyring")

        policy = get_signing_policy(path, keyring)
        policy(content, path)

        mock_policy_read_signed.assert_called_once_with(
            content, path, keyring=keyring
        )


class TestGetOSFromProduct:
    def test_returns_os_from_product(self):
        os = factory.make_name("os")
        product = {"os": os}
        assert os == get_os_from_product(product)

    def test_returns_ubuntu_if_missing(self):
        assert "ubuntu" == get_os_from_product({})
