# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from functools import partial
import hashlib
import json
import os
from random import randint
from unittest.mock import ANY, Mock, sentinel

import httplib2

from apiclient.testing.credentials import make_api_credentials
from maascli.actions import boot_resources_create
from maascli.actions.boot_resources_create import (
    BootResourcesCreateAction,
    CHUNK_SIZE,
)
from maascli.command import CommandError
from maastesting.factory import factory
from maastesting.fixtures import CaptureStandardIO, TempDirectory
from maastesting.testcase import MAASTestCase


class TestBootResourcesCreateAction(MAASTestCase):
    """Tests for `BootResourcesCreateAction`."""

    def configure_http_request(self, status, content):
        self.assertIsInstance(content, bytes)
        response = httplib2.Response(
            {"status": status, "content-type": "text/plain"}
        )
        http_request = self.patch(boot_resources_create, "http_request")
        http_request.return_value = (response, content)

    def make_boot_resources_create_action(self):
        self.stdio = self.useFixture(CaptureStandardIO())
        action_bases = (BootResourcesCreateAction,)
        action_ns = {
            "action": {"method": "POST"},
            "handler": {
                "path": b"/MAAS/api/2.0/boot-resources/",
                "params": [],
            },
            "profile": {
                "credentials": make_api_credentials(),
                "url": "http://localhost",
            },
        }
        action_class = type("create", action_bases, action_ns)
        action = action_class(Mock())
        return action

    def make_content(self, size=None):
        tmpdir = self.useFixture(TempDirectory()).path
        if size is None:
            size = randint(1024, 2048)
        data = factory.make_bytes(size)
        content_path = os.path.join(tmpdir, "content")
        with open(content_path, "wb") as stream:
            stream.write(data)
        sha256 = hashlib.sha256()
        sha256.update(data)
        return size, sha256.hexdigest(), partial(open, content_path, "rb")

    def test_initial_request_returns_content(self):
        content = factory.make_name("content")
        self.configure_http_request(200, content.encode("ascii"))
        action = self.make_boot_resources_create_action()
        self.patch(action, "prepare_initial_payload").return_value = ("", {})
        self.assertEqual(
            content.encode("ascii"),
            action.initial_request(Mock(), "http://example.com", Mock()),
        )

    def test_initial_request_raises_CommandError_on_error(self):
        self.configure_http_request(
            500, factory.make_name("content").encode("ascii")
        )
        action = self.make_boot_resources_create_action()
        self.patch(action, "prepare_initial_payload").return_value = ("", {})
        self.assertRaises(
            CommandError,
            action.initial_request,
            Mock(),
            "http://example.com",
            Mock(),
        )

    def test_prepare_initial_payload_raises_CommandError_missing_content(self):
        action = self.make_boot_resources_create_action()
        self.patch(boot_resources_create, "print")
        self.assertRaises(
            CommandError, action.prepare_initial_payload, [("invalid", "")]
        )

    def test_prepare_initial_payload_adds_size_and_sha256(self):
        size, sha256, stream = self.make_content()
        action = self.make_boot_resources_create_action()
        mock_build_message = self.patch(
            boot_resources_create, "build_multipart_message"
        )
        self.patch(
            boot_resources_create, "encode_multipart_message"
        ).return_value = (None, None)
        action.prepare_initial_payload([("content", stream)])
        mock_build_message.assert_called_once_with(
            [("sha256", sha256), ("size", "%s" % size)],
        )

    def test_get_resource_file_returns_None_when_no_sets(self):
        content = {"sets": {}}
        action = self.make_boot_resources_create_action()
        self.assertIsNone(action.get_resource_file(json.dumps(content)))

    def test_get_resource_file_returns_None_when_no_files(self):
        content = {"sets": {"20140910": {"files": {}}}}
        action = self.make_boot_resources_create_action()
        self.assertIsNone(action.get_resource_file(json.dumps(content)))

    def test_get_resource_file_returns_None_when_more_than_one_file(self):
        content = {
            "sets": {
                "20140910": {"files": {"root-image.gz": {}, "root-tgz": {}}}
            }
        }
        action = self.make_boot_resources_create_action()
        self.assertIsNone(action.get_resource_file(json.dumps(content)))

    def test_get_resource_file_returns_file_from_newest_set(self):
        filename = factory.make_name("file")
        content = {
            "sets": {
                "20140910": {"files": {filename: {"name": filename}}},
                "20140909": {"files": {"other": {"name": "other"}}},
            }
        }
        action = self.make_boot_resources_create_action()
        self.assertEqual(
            {"name": filename}, action.get_resource_file(json.dumps(content))
        )

    def test_get_resource_file_accepts_bytes(self):
        filename = factory.make_name("file")
        content = {
            "sets": {
                "20140910": {"files": {filename: {"name": filename}}},
                "20140909": {"files": {"other": {"name": "other"}}},
            }
        }
        action = self.make_boot_resources_create_action()
        self.assertEqual(
            {"name": filename},
            action.get_resource_file(json.dumps(content).encode("utf-8")),
        )

    def test_put_upload_raise_CommandError_if_status_not_200(self):
        self.configure_http_request(500, b"")
        action = self.make_boot_resources_create_action()
        self.assertRaises(
            CommandError, action.put_upload, Mock(), "http://example.com", b""
        )

    def test_put_upload_sends_content_type_and_length_headers(self):
        response = httplib2.Response({"status": 200})
        mock_request = self.patch(boot_resources_create, "http_request")
        mock_request.return_value = (response, b"")
        action = self.make_boot_resources_create_action()
        self.patch(action, "sign")
        data = factory.make_bytes()
        action.put_upload(Mock(), "http://example.com", data)
        headers = {
            "Content-Type": "application/octet-stream",
            "Content-Length": "%s" % len(data),
        }
        mock_request.assert_called_once_with(
            "http://example.com",
            "PUT",
            body=ANY,
            headers=headers,
            client=ANY,
        )

    def test_upload_content_calls_put_upload_with_sizeof_CHUNK_SIZE(self):
        size = CHUNK_SIZE * 2
        size, sha256, stream = self.make_content(size=size)
        action = self.make_boot_resources_create_action()
        mock_upload = self.patch(action, "put_upload")
        action.upload_content(Mock(), sentinel.upload_uri, stream)

        call_data_sizes = [
            len(call[0][2]) for call in mock_upload.call_args_list
        ]
        self.assertEqual([CHUNK_SIZE, CHUNK_SIZE], call_data_sizes)

    def test_uses_cacerts(self):
        action = self.make_boot_resources_create_action()
        self.patch(action, "initial_request")
        self.patch(action, "get_resource_file")
        self.patch(action, "put_upload")
        mock_materializer = self.patch(
            boot_resources_create, "materialize_certificate"
        )
        mock_materializer.return_value = None

        action(Mock())
        mock_materializer.assert_called_once()
