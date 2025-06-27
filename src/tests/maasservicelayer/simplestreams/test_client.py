# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from asyncio.subprocess import Process
import json
from unittest.mock import AsyncMock

import pytest

from maasservicelayer.simplestreams.client import (
    SIGNED_INDEX_PATH,
    SimpleStreamsClient,
    SimpleStreamsClientException,
)
from maasservicelayer.simplestreams.models import (
    SimpleStreamsProductListFactory,
)

SAMPLE_INDEX = {
    "format": "index:1.0",
    "index": {
        "com.ubuntu.maas:stable:1:bootloader-download": {
            "datatype": "image-ids",
            "format": "products:1.0",
            "path": "streams/v1/com.ubuntu.maas:stable:1:bootloader-download.sjson",
            "products": [],
            "updated": "Wed, 25 Jun 2025 11:01:49 +0000",
        },
        "com.ubuntu.maas:stable:centos-bases-download": {
            "datatype": "image-ids",
            "format": "products:1.0",
            "path": "streams/v1/com.ubuntu.maas:stable:centos-bases-download.sjson",
            "products": [],
            "updated": "Wed, 25 Jun 2025 11:01:49 +0000",
        },
        "com.ubuntu.maas:stable:v3:download": {
            "datatype": "image-ids",
            "format": "products:1.0",
            "path": "streams/v1/com.ubuntu.maas:stable:v3:download.sjson",
            "products": [],
            "updated": "Wed, 25 Jun 2025 11:01:49 +0000",
        },
    },
    "updated": "Wed, 25 Jun 2025 11:01:49 +0000",
}

SIGNED_SAMPLE_INDEX = f"""\
-----BEGIN PGP SIGNED MESSAGE-----
Hash: SHA512

{json.dumps(SAMPLE_INDEX)}

-----BEGIN PGP SIGNATURE-----

abcdef0123456789
-----END PGP SIGNATURE-----
"""

UNSIGNED_INDEX_PATH = "streams/v1/index.json"


class TestSimpleStreamsClient:
    async def test_init(self, mocker) -> None:
        c1 = SimpleStreamsClient(
            url="http://foo.com", skip_pgp_verification=True
        )
        mocker.patch("os.path.exists").side_effect = [True, False]
        c2 = SimpleStreamsClient(
            url="http://foo.com",
            skip_pgp_verification=False,
            keyring_file="/path/to/existing/file",
        )
        with pytest.raises(SimpleStreamsClientException) as e:
            # keyring file doesn't exists
            SimpleStreamsClient(
                url="http://foo.com",
                skip_pgp_verification=False,
                keyring_file="/path/to/non-existing/file",
            )

        assert (
            str(e.value)
            == "The path to the keyring file '/path/to/non-existing/file' doesn't exists."
        )
        with pytest.raises(SimpleStreamsClientException) as e:
            # keyring file is None but we have to verify pgp signature
            SimpleStreamsClient(
                url="http://foo.com",
                skip_pgp_verification=False,
                keyring_file=None,
            )
        assert (
            str(e.value)
            == "'keyring_file' cannot be None if pgp verification is enabled."
        )
        await c1.close_session()
        await c2.close_session()

    async def test_default_index_based_on_url(self, mocker) -> None:
        mocker.patch("os.path.exists").return_value = True
        c1 = SimpleStreamsClient(
            url="http://foo.com", keyring_file="/path/to/keyring"
        )
        assert c1._index_path == SIGNED_INDEX_PATH

        c2 = SimpleStreamsClient(
            url="http://foo.com/streams/v1/index-custom.sjson",
            keyring_file="/path/to/keyring",
        )
        assert c2._index_path == "streams/v1/index-custom.sjson"

        c3 = SimpleStreamsClient(
            url="http://foo.com/streams/v1/index.json",
            keyring_file="/path/to/keyring",
        )
        assert c3._index_path == "streams/v1/index.json"

        await c1.close_session()
        await c2.close_session()
        await c3.close_session()

    async def test_validate_pgp_signature_no_gpg_executable_found(
        self, mocker
    ) -> None:
        mocker.patch("os.path.exists").return_value = True
        mocker.patch("shutil.which").side_effect = [None, None]
        async with SimpleStreamsClient(
            url="http://foo.com",
            keyring_file="/path/to/keyring",
        ) as client:
            with pytest.raises(SimpleStreamsClientException) as e:
                await client._validate_pgp_signature("test")
        assert (
            str(e.value) == "Either 'gpg' or 'gpgv' command must be available."
        )

    @pytest.mark.parametrize(
        "which_output, expected_cmd",
        [
            (
                ["/usr/bin/gpgv", None],
                ["gpgv", "--keyring=/path/to/keyring", "-"],
            ),
            (
                [None, "/usr/bin/gpg"],
                ["gpg", "--verify", "--keyring=/path/to/keyring", "-"],
            ),
        ],
    )
    async def test_validate_pgp_signature(
        self, mocker, which_output: list, expected_cmd: list[str]
    ) -> None:
        mocker.patch("os.path.exists").return_value = True
        mocker.patch("shutil.which").side_effect = which_output
        process_mock = AsyncMock(Process)
        process_mock.returncode = 0
        process_mock.communicate.return_value = (
            b'gpgv: Good signature from "Jane Doe <jane@doe.com>"',
            b"",
        )

        asyncio_create_subp_mock = mocker.patch(
            "asyncio.create_subprocess_exec"
        )
        asyncio_create_subp_mock.return_value = process_mock

        async with SimpleStreamsClient(
            url="http://foo.com",
            keyring_file="/path/to/keyring",
        ) as client:
            await client._validate_pgp_signature("test")

        asyncio_create_subp_mock.assert_called_once_with(
            *expected_cmd,
            stdin=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    async def test_validate_pgp_signature_invalid(self, mocker) -> None:
        mocker.patch("os.path.exists").return_value = True
        mocker.patch("shutil.which").return_value = "/usr/bin/gpgv"
        process_mock = AsyncMock(Process)
        process_mock.returncode = 1
        err_msg = b"gpgv: Can't check signature: No public key"
        process_mock.communicate.return_value = (b"", err_msg)

        asyncio_create_subp_mock = mocker.patch(
            "asyncio.create_subprocess_exec"
        )
        asyncio_create_subp_mock.return_value = process_mock

        async with SimpleStreamsClient(
            url="http://foo.com",
            keyring_file="/path/to/keyring",
        ) as client:
            with pytest.raises(SimpleStreamsClientException) as e:
                await client._validate_pgp_signature("test")

        assert str(e.value) == f"Failed to verify PGP signature: {err_msg}"

    @pytest.mark.parametrize(
        "response, skip_verification",
        [
            (
                (
                    "-----BEGIN PGP SIGNED MESSAGE-----\n"
                    "Hash: SHA512\n\n"
                    '{"foo": "bar"}\n'
                    "-----BEGIN PGP SIGNATURE-----\n\n"
                    "abcde1234567890\n"
                    "-----END PGP SIGNATURE-----"
                ),
                False,
            ),
            ('{"foo":"bar"}', True),
        ],
    )
    async def test_parse_response(
        self, response: str, skip_verification: bool, mocker
    ) -> None:
        mocker.patch("os.path.exists").return_value = True
        async with SimpleStreamsClient(
            url="http://foo.com",
            skip_pgp_verification=skip_verification,
            keyring_file="/path/to/keyring",
        ) as client:
            mocker.patch.object(
                client, "_validate_pgp_signature"
            ).return_value = None
            data = await client._parse_response(response)

        assert data == {"foo": "bar"}

    async def test_parse_response_tries_to_verify_unsigned_index(
        self, mocker
    ) -> None:
        mocker.patch("os.path.exists").return_value = True
        url = f"http://foo.com/{UNSIGNED_INDEX_PATH}"
        response = json.dumps(SAMPLE_INDEX)
        async with SimpleStreamsClient(
            url=url, keyring_file="/path/to/keyring"
        ) as client:
            mocker.patch.object(
                client, "_validate_pgp_signature"
            ).side_effect = SimpleStreamsClientException(
                "Failed to verify PGP signature: gpgv: no valid OpenPGP data found."
            )
            with pytest.raises(SimpleStreamsClientException):
                await client._parse_response(response)

    async def test_http_get_uses_proxy(self, mock_aioresponse) -> None:
        url = "http://foo.com"
        mock_aioresponse.get(url, payload="")
        async with SimpleStreamsClient(
            url=url, skip_pgp_verification=True, http_proxy="http://proxy.com"
        ) as client:
            await client.http_get(url)
        mock_aioresponse.assert_called_with(
            url=url,
            proxy="http://proxy.com",
            method="GET",
        )

    async def test_http_get_raise_status(self, mock_aioresponse) -> None:
        url = "http://foo.com"
        mock_aioresponse.get(url, status=404)
        async with SimpleStreamsClient(
            url=url,
            skip_pgp_verification=True,
        ) as client:
            with pytest.raises(SimpleStreamsClientException) as e:
                await client.http_get(url)
        mock_aioresponse.assert_called_with(
            url=url,
            proxy=None,
            method="GET",
        )
        assert str(e.value) == f"Request to '{url}' failed: 404 Not Found"

    async def test_get_index(self, mocker, mock_aioresponse) -> None:
        mocker.patch("os.path.exists").return_value = True
        url = "http://foo.com"
        mock_aioresponse.get(
            f"{url}/{SIGNED_INDEX_PATH}", body=SIGNED_SAMPLE_INDEX
        )
        async with SimpleStreamsClient(
            url=url, keyring_file="/path/to/keyring"
        ) as client:
            mocker.patch.object(
                client, "_validate_pgp_signature"
            ).return_value = None
            await client.get_index()
        mock_aioresponse.assert_called_with(
            url=f"{url}/{SIGNED_INDEX_PATH}",
            proxy=None,
            method="GET",
        )

    async def test_get_index_skip_verification(self, mock_aioresponse) -> None:
        url = "http://foo.com"
        mock_aioresponse.get(
            f"{url}/{SIGNED_INDEX_PATH}", payload=SAMPLE_INDEX
        )
        async with SimpleStreamsClient(
            url=url, skip_pgp_verification=True
        ) as client:
            await client.get_index()
        mock_aioresponse.assert_called_with(
            url=f"{url}/{SIGNED_INDEX_PATH}",
            proxy=None,
            method="GET",
        )

    async def test_get_product(self, mocker, mock_aioresponse) -> None:
        mocker.patch("os.path.exists").return_value = True
        url = "http://foo.com"
        product_path = (
            "streams/v1/com.ubuntu.maas:stable:1:bootloader-download.sjson"
        )
        mock_aioresponse.get(f"{url}/{product_path}", payload={})
        # patch the factory to not raise errors as there are no products
        mocker.patch.object(
            SimpleStreamsProductListFactory, "produce"
        ).return_value = None
        async with SimpleStreamsClient(
            url=url, keyring_file="/path/to/keyring"
        ) as client:
            mocker.patch.object(
                client, "_validate_pgp_signature"
            ).return_value = None
            await client.get_product(product_path)
        mock_aioresponse.assert_called_with(
            url=f"{url}/{product_path}",
            proxy=None,
            method="GET",
        )

    async def test_get_all_products(self, mocker, mock_aioresponse) -> None:
        mocker.patch("os.path.exists").return_value = True
        url = "http://foo.com"
        product_paths = [v["path"] for v in SAMPLE_INDEX["index"].values()]
        mock_aioresponse.get(
            f"{url}/{SIGNED_INDEX_PATH}", body=SIGNED_SAMPLE_INDEX
        )
        for path in product_paths:
            mock_aioresponse.get(f"{url}/{path}", payload={})
        # patch the factory to not raise errors as there are no products
        mocker.patch.object(
            SimpleStreamsProductListFactory, "produce"
        ).return_value = None
        async with SimpleStreamsClient(
            url=url, keyring_file="/path/to/keyring"
        ) as client:
            mocker.patch.object(
                client, "_validate_pgp_signature"
            ).return_value = None
            await client.get_all_products()

        mock_aioresponse.assert_called_with(
            url=f"{url}/{SIGNED_INDEX_PATH}",
            proxy=None,
            method="GET",
        )

        for path in product_paths:
            mock_aioresponse.assert_called_with(
                url=f"{url}/{path}",
                proxy=None,
                method="GET",
            )
