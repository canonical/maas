# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS Boot Resources Action."""

import hashlib
from io import BytesIO
import json
from urllib.parse import urljoin

import httplib2

from apiclient.multipart import (
    build_multipart_message,
    encode_multipart_message,
)
from maascli import utils
from maascli.api import Action, http_request, materialize_certificate
from maascli.command import CommandError

# Send 4MB of data per request.
CHUNK_SIZE = 1 << 22


class BootResourcesCreateAction(Action):
    """Provides custom logic to the boot-resources create action.

    Command: maas username boot-resources create

    The create command has the ability to upload the content in pieces, using
    the upload_uri that is returned in the response. This class provides the
    logic to upload over that API.
    """

    def __call__(self, options):
        client = httplib2.Http(
            ca_certs=materialize_certificate(self.profile),
            disable_ssl_certificate_validation=options.insecure,
        )

        # TODO: this is el-cheapo URI Template
        # <http://tools.ietf.org/html/rfc6570> support; use uritemplate-py
        # <https://github.com/uri-templates/uritemplate-py> here?
        uri = self.uri.format(**vars(options))
        content = self.initial_request(client, uri, options)

        # Get the created resource file for the boot resource
        rfile = self.get_resource_file(content)
        if rfile is None:
            print("Failed to identify created resource.")
            raise CommandError(2)
        if rfile["complete"]:
            # File already existed in the database, so no
            # reason to upload it.
            return

        # Upload content
        data = dict(options.data)
        upload_uri = urljoin(uri, rfile["upload_uri"])
        self.upload_content(client, upload_uri, data["content"])

    def initial_request(self, client, uri, options):
        """Performs the initial POST request, to create the boot resource."""
        # Bundle things up ready to throw over the wire.
        body, headers = self.prepare_initial_payload(options.data)

        # Headers are returned as a list, but they must be a dict for
        # the signing machinery.
        headers = dict(headers)

        # Sign request if credentials have been provided.
        if self.credentials is not None:
            self.sign(uri, headers, self.credentials)

        # Use httplib2 instead of urllib2 (or MAASDispatcher, which is based
        # on urllib2) so that we get full control over HTTP method. TODO:
        # create custom MAASDispatcher to use httplib2 so that MAASClient can
        # be used.
        response, content = http_request(
            uri,
            self.method,
            body=body,
            headers=headers,
            client=client,
        )

        # 2xx status codes are all okay.
        if response.status // 100 != 2:
            if options.debug:
                utils.dump_response_summary(response)
            utils.print_response_content(response, content)
            raise CommandError(2)
        return content

    def prepare_initial_payload(self, data):
        """Return the body and headers for the initial request.

        This is method is only used for the first request to MAAS. It
        removes the passed content, and replaces it with the sha256 and size
        of that content.

        :param data: An iterable of ``name, value`` or ``name, opener``
            tuples (see `name_value_pair`) to pack into the body or
            query, depending on the type of request.
        """
        data = dict(data)
        if "content" not in data:
            print("Missing content.")
            raise CommandError(2)

        content = data.pop("content")
        size, sha256 = self.calculate_size_and_sha256(content)
        data["size"] = "%s" % size
        data["sha256"] = sha256

        data = sorted((key, value) for key, value in data.items())
        message = build_multipart_message(data)
        headers, body = encode_multipart_message(message)
        return body, headers

    def calculate_size_and_sha256(self, content):
        """Return the size and sha256 of the content."""
        size = 0
        sha256 = hashlib.sha256()
        with content() as fd:
            while True:
                buf = fd.read(CHUNK_SIZE)
                length = len(buf)
                size += length
                sha256.update(buf)
                if length != CHUNK_SIZE:
                    break
        return size, sha256.hexdigest()

    def get_resource_file(self, content):
        """Return the boot resource file for the created file."""
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        data = json.loads(content)
        if len(data["sets"]) == 0:
            # No sets returned, no way to get the resource file.
            return None
        newest_set = sorted(data["sets"].keys(), reverse=True)[0]
        resource_set = data["sets"][newest_set]
        if len(resource_set["files"]) != 1:
            # This api only supports uploading one file. If the set doesn't
            # have just one file, then there is no way of knowing which file.
            return None
        _, rfile = resource_set["files"].popitem()
        return rfile

    def put_upload(self, client, upload_uri, data):
        """Send PUT method to upload data."""
        headers = {
            "Content-Type": "application/octet-stream",
            "Content-Length": "%s" % len(data),
        }
        if self.credentials is not None:
            self.sign(upload_uri, headers, self.credentials)
        # httplib2 expects the body to be file-like if its binary data
        data = BytesIO(data)
        response, content = http_request(
            upload_uri,
            "PUT",
            body=data,
            headers=headers,
            client=client,
        )
        if response.status != 200:
            utils.print_response_content(response, content)
            raise CommandError(2)

    def upload_content(self, client, upload_uri, content):
        """Upload the content in chunks."""
        with content() as fd:
            while True:
                buf = fd.read(CHUNK_SIZE)
                length = len(buf)
                if length > 0:
                    self.put_upload(client, upload_uri, buf)
                if length != CHUNK_SIZE:
                    break


# Each action sets this variable so the class can be picked up
# by get_action_class.
action_class = BootResourcesCreateAction
