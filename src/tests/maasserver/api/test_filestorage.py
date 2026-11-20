# Copyright 2013-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for file-storage API."""

from base64 import b64decode
import http.client

from django.urls import reverse

from maasserver.models import FileStorage
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes
from maastesting.utils import sample_binary_data


class FileStorageAPITestMixin:
    def _create_API_params(self, op=None, filename=None, fileObj=None):
        params = {}
        if op is not None:
            params["op"] = op
        if filename is not None:
            params["filename"] = filename
        if fileObj is not None:
            params["file"] = fileObj
        return params

    def make_API_POST_request(self, op=None, filename=None, fileObj=None):
        """Make an API POST request and return the response."""
        params = self._create_API_params(op, filename, fileObj)
        return self.client.post(reverse("files_handler"), params)

    def make_API_GET_request(self, op=None, filename=None, fileObj=None):
        """Make an API GET request and return the response."""
        params = self._create_API_params(op, filename, fileObj)
        return self.client.get(reverse("files_handler"), params)


class TestAnonymousFileStorageAPI(
    FileStorageAPITestMixin, APITestCase.ForAnonymous
):
    def test_get_does_not_work_anonymously(self):
        storage = factory.make_FileStorage()
        response = self.make_API_GET_request("get", storage.filename)
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)

    def test_get_by_key_works_anonymously(self):
        storage = factory.make_FileStorage()
        response = self.client.get(
            reverse("files_handler"), {"key": storage.key, "op": "get_by_key"}
        )

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(storage.content, response.content)

    def test_anon_resource_uri_allows_anonymous_access(self):
        storage = factory.make_FileStorage()
        response = self.client.get(storage.anon_resource_uri)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(storage.content, response.content)

    def test_anon_cannot_list_files(self):
        factory.make_FileStorage()
        response = self.make_API_GET_request("list")
        # The 'list' operation is not available to anon users.
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)

    def test_anon_cannot_get_file(self):
        storage = factory.make_FileStorage()
        response = self.client.get(
            reverse("file_handler", args=[storage.filename])
        )
        self.assertEqual(http.client.UNAUTHORIZED, response.status_code)

    def test_anon_cannot_delete_file(self):
        storage = factory.make_FileStorage()
        response = self.client.delete(
            reverse("file_handler", args=[storage.filename])
        )
        self.assertEqual(http.client.UNAUTHORIZED, response.status_code)


class TestFileStorageAPI(FileStorageAPITestMixin, APITestCase.ForUser):
    def test_files_handler_path(self):
        self.assertEqual("/MAAS/api/2.0/files/", reverse("files_handler"))

    def test_file_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/files/filename/",
            reverse("file_handler", args=["filename"]),
        )

    def test_add_file_succeeds(self):
        response = self.make_API_POST_request(
            None, factory.make_name("upload"), factory.make_file_upload()
        )
        self.assertEqual(http.client.CREATED, response.status_code)

    def test_add_file_with_slashes_in_name_succeeds(self):
        filename = "filename/with/slashes/in/it"
        response = self.make_API_POST_request(
            None, filename, factory.make_file_upload()
        )
        self.assertEqual(http.client.CREATED, response.status_code)
        self.assertCountEqual(
            [filename],
            FileStorage.objects.filter(filename=filename).values_list(
                "filename", flat=True
            ),
        )

    def test_add_file_fails_with_no_filename(self):
        response = self.make_API_POST_request(
            None, fileObj=factory.make_file_upload()
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertIn("text/plain", response["Content-Type"])
        self.assertEqual(b"Filename not supplied", response.content)

    def test_add_empty_file(self):
        filename = "filename"
        response = self.make_API_POST_request(
            None,
            filename=filename,
            fileObj=factory.make_file_upload(content=b""),
        )
        self.assertEqual(http.client.CREATED, response.status_code)
        self.assertCountEqual(
            [filename],
            FileStorage.objects.filter(filename=filename).values_list(
                "filename", flat=True
            ),
        )

    def test_add_file_fails_with_no_file_attached(self):
        response = self.make_API_POST_request(None, "foo")

        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertIn("text/plain", response["Content-Type"])
        self.assertEqual(b"File not supplied", response.content)

    def test_add_file_fails_with_too_many_files(self):
        foo = factory.make_file_upload(name="foo")
        foo2 = factory.make_file_upload(name="foo2")

        response = self.client.post(
            reverse("files_handler"),
            {"filename": "foo", "file": foo, "file2": foo2},
        )

        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertIn("text/plain", response["Content-Type"])
        self.assertEqual(
            b"Exactly one file must be supplied", response.content
        )

    def test_add_file_can_overwrite_existing_file_of_same_name(self):
        # Write file one.
        response = self.make_API_POST_request(
            None, "foo", factory.make_file_upload(content=b"file one")
        )
        self.assertEqual(http.client.CREATED, response.status_code)

        # Write file two with the same name but different contents.
        response = self.make_API_POST_request(
            None, "foo", factory.make_file_upload(content=b"file two")
        )
        self.assertEqual(http.client.CREATED, response.status_code)

        # Retrieve the file and check its contents are the new contents.
        response = self.make_API_GET_request("get", "foo")
        self.assertEqual(b"file two", response.content)

    def test_get_file_succeeds(self):
        filename = factory.make_name("file")
        factory.make_FileStorage(
            filename=filename, content=b"give me rope", owner=self.user
        )
        response = self.make_API_GET_request("get", filename)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(b"give me rope", response.content)

    def test_get_file_checks_owner(self):
        filename = factory.make_name("file")
        factory.make_FileStorage(
            filename=filename,
            content=b"give me rope",
            owner=factory.make_User(),
        )
        response = self.make_API_GET_request("get", filename)

        self.assertEqual(http.client.NOT_FOUND, response.status_code)

    def test_get_fetches_the_most_recent_file(self):
        filename = factory.make_name("file")
        factory.make_FileStorage(filename=filename, owner=self.user)
        storage = factory.make_FileStorage(filename=filename, owner=self.user)
        response = self.make_API_GET_request("get", filename)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(storage.content, response.content)

    def test_get_file_fails_with_no_filename(self):
        response = self.make_API_GET_request("get")

        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertIn("text/plain", response["Content-Type"])
        self.assertEqual(b"No provided filename!", response.content)

    def test_get_file_fails_with_missing_file(self):
        response = self.make_API_GET_request("get", filename="missingfilename")

        self.assertEqual(http.client.NOT_FOUND, response.status_code)
        self.assertIn("text/plain", response["Content-Type"])
        self.assertEqual(b"File not found", response.content)

    def test_list_files_returns_ordered_list(self):
        filenames = ["myfiles/a", "myfiles/z", "myfiles/b"]
        for filename in filenames:
            factory.make_FileStorage(
                filename=filename, content=b"test content", owner=self.user
            )
        response = self.make_API_GET_request()
        self.assertEqual(http.client.OK, response.status_code)
        parsed_results = json_load_bytes(response.content)
        filenames = [result["filename"] for result in parsed_results]
        self.assertEqual(sorted(filenames), filenames)

    def test_list_files_filters_by_owner(self):
        factory.make_FileStorage(owner=factory.make_User())
        response = self.make_API_GET_request()
        self.assertEqual(http.client.OK, response.status_code)
        parsed_results = json_load_bytes(response.content)
        self.assertEqual([], parsed_results)

    def test_list_files_lists_files_with_prefix(self):
        filenames_with_prefix = ["prefix-file1", "prefix-file2"]
        filenames = filenames_with_prefix + ["otherfile", "otherfile2"]
        for filename in filenames:
            factory.make_FileStorage(
                filename=filename, content=b"test content", owner=self.user
            )
        response = self.client.get(
            reverse("files_handler"), {"prefix": "prefix-"}
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_results = json_load_bytes(response.content)
        filenames = [result["filename"] for result in parsed_results]
        self.assertCountEqual(filenames_with_prefix, filenames)

    def test_list_files_does_not_include_file_content(self):
        factory.make_FileStorage(
            filename="filename", content=b"test content", owner=self.user
        )
        response = self.make_API_GET_request()
        parsed_results = json_load_bytes(response.content)
        self.assertNotIn("content", parsed_results[0])

    def test_files_resource_uri_supports_slashes_in_filenames(self):
        filename = "a/filename/with/slashes/in/it/"
        factory.make_FileStorage(
            filename=filename, content=b"test content", owner=self.user
        )
        response = self.make_API_GET_request()
        parsed_results = json_load_bytes(response.content)
        resource_uri = parsed_results[0]["resource_uri"]
        expected_uri = reverse("file_handler", args=[filename])
        self.assertEqual(expected_uri, resource_uri)

    def test_api_supports_slashes_in_filenames_roundtrip_test(self):
        # Do a roundtrip (upload a file then get it) for a file with a
        # name that contains slashes.
        filename = "filename/with/slashes/in/it"
        self.make_API_POST_request(None, filename, factory.make_file_upload())
        file_url = reverse("file_handler", args=[filename])
        # The file url contains the filename without any kind of
        # escaping.
        self.assertIn(filename, file_url)
        response = self.client.get(file_url)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(filename, parsed_result["filename"])

    def test_get_file_returns_file_object_with_content_base64_encoded(self):
        filename = factory.make_name("file")
        content = sample_binary_data
        factory.make_FileStorage(
            filename=filename, content=content, owner=self.user
        )
        response = self.client.get(reverse("file_handler", args=[filename]))
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(
            (filename, content),
            (parsed_result["filename"], b64decode(parsed_result["content"])),
        )

    def test_get_file_returns_file_object_with_resource_uri(self):
        filename = factory.make_name("file")
        content = sample_binary_data
        factory.make_FileStorage(
            filename=filename, content=content, owner=self.user
        )
        response = self.client.get(reverse("file_handler", args=[filename]))
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(
            reverse("file_handler", args=[filename]),
            parsed_result["resource_uri"],
        )

    def test_get_file_returns_owned_file(self):
        # If both an owned file and a non-owned file are present (with the
        # same name), the owned file is returned.
        filename = factory.make_name("file")
        factory.make_FileStorage(filename=filename, owner=None)
        content = sample_binary_data
        storage = factory.make_FileStorage(
            filename=filename, content=content, owner=self.user
        )
        response = self.client.get(reverse("file_handler", args=[filename]))
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(
            (filename, storage.anon_resource_uri, content),
            (
                parsed_result["filename"],
                parsed_result["anon_resource_uri"],
                b64decode(parsed_result["content"]),
            ),
        )

    def test_get_file_returning_404_file_includes_header(self):
        # In order to fix bug 1123986 we need to distinguish between
        # a 404 returned when the file is not present and a 404 returned
        # when the API endpoint is not present.  We do this by setting
        # a header: "Workaround: bug1123986".
        response = self.client.get(
            reverse("file_handler", args=[factory.make_name("file")])
        )
        self.assertEqual(response.status_code, http.client.NOT_FOUND)
        self.assertEqual(response.get("Workaround"), "bug1123986")

    def test_delete_filters_by_owner(self):
        storage = factory.make_FileStorage(owner=factory.make_User())
        response = self.client.delete(
            reverse("file_handler", args=[storage.filename])
        )
        self.assertEqual(http.client.NOT_FOUND, response.status_code)
        files = FileStorage.objects.filter(filename=storage.filename)
        self.assertEqual([storage], list(files))

    def test_delete_file_deletes_file(self):
        filename = factory.make_name("file")
        factory.make_FileStorage(
            filename=filename, content=b"test content", owner=self.user
        )
        response = self.client.delete(reverse("file_handler", args=[filename]))
        self.assertEqual(http.client.NO_CONTENT, response.status_code)
        files = FileStorage.objects.filter(filename=filename)
        self.assertEqual([], list(files))

    def test_delete_on_files(self):
        filename = factory.make_name("file")
        factory.make_FileStorage(
            filename=filename, content=b"test content", owner=self.user
        )
        response = self.client.delete(
            reverse("files_handler"), query={"filename": filename}
        )

        self.assertEqual(http.client.NO_CONTENT, response.status_code)
        files = FileStorage.objects.filter(filename=filename)
        self.assertEqual([], list(files))
