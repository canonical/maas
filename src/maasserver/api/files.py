# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `File`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'FileHandler',
    'FilesHandler',
    ]

from base64 import b64encode
import httplib

from django.core.urlresolvers import reverse
from django.http import (
    Http404,
    HttpResponse,
)
from django.shortcuts import get_object_or_404
from maasserver.api.support import (
    AnonymousOperationsHandler,
    operation,
    OperationsHandler,
)
from maasserver.api.utils import get_mandatory_param
from maasserver.exceptions import (
    MAASAPIBadRequest,
    MAASAPINotFound,
)
from maasserver.models import FileStorage
from piston.emitters import JSONEmitter
from piston.handler import typemapper
from piston.utils import rc


def get_file_by_name(handler, request):
    """Get a named file from the file storage.

    :param filename: The exact name of the file you want to get.
    :type filename: string
    :return: The file is returned in the response content.
    """
    filename = get_mandatory_param(request.GET, 'filename')
    try:
        db_file = FileStorage.objects.filter(filename=filename).latest('id')
    except FileStorage.DoesNotExist:
        raise MAASAPINotFound("File not found")
    return HttpResponse(db_file.content, status=httplib.OK)


def get_file_by_key(handler, request):
    """Get a file from the file storage using its key.

    :param key: The exact key of the file you want to get.
    :type key: string
    :return: The file is returned in the response content.
    """
    key = get_mandatory_param(request.GET, 'key')
    db_file = get_object_or_404(FileStorage, key=key)
    return HttpResponse(db_file.content, status=httplib.OK)


class AnonFilesHandler(AnonymousOperationsHandler):
    """Anonymous file operations.

    This is needed for Juju. The story goes something like this:

    - The Juju provider will upload a file using an "unguessable" name.

    - The name of this file (or its URL) will be shared with all the agents in
      the environment. They cannot modify the file, but they can access it
      without credentials.

    """
    create = read = update = delete = None

    get_by_name = operation(
        idempotent=True, exported_as='get')(get_file_by_name)
    get_by_key = operation(
        idempotent=True, exported_as='get_by_key')(get_file_by_key)

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('files_handler', [])


# DISPLAYED_FILES_FIELDS_OBJECT is the list of fields used when dumping
# lists of FileStorage objects.
DISPLAYED_FILES_FIELDS = ('filename', 'anon_resource_uri')


def json_file_storage(stored_file, request):
    # Convert stored_file into a json object: use the same fields used
    # when serialising lists of object, plus the base64-encoded content.
    dict_representation = {
        fieldname: getattr(stored_file, fieldname)
        for fieldname in DISPLAYED_FILES_FIELDS
        }
    # Encode the content as base64.
    dict_representation['content'] = b64encode(
        getattr(stored_file, 'content'))
    dict_representation['resource_uri'] = reverse(
        'file_handler', args=[stored_file.filename])
    # Emit the json for this object manually because, no matter what the
    # piston documentation says, once a type is associated with a list
    # of fields by piston's typemapper mechanism, there is no way to
    # override that in a specific handler with 'fields' or 'exclude'.
    emitter = JSONEmitter(dict_representation, typemapper, None)
    stream = emitter.render(request)
    return stream


class FileHandler(OperationsHandler):
    """Manage a FileStorage object.

    The file is identified by its filename and owner.
    """
    api_doc_section_name = "File"
    model = FileStorage
    fields = DISPLAYED_FILES_FIELDS
    create = update = None

    def read(self, request, filename):
        """GET a FileStorage object as a json object.

        The 'content' of the file is base64-encoded."""
        try:
            stored_file = get_object_or_404(
                FileStorage, filename=filename, owner=request.user)
        except Http404:
            # In order to fix bug 1123986 we need to distinguish between
            # a 404 returned when the file is not present and a 404 returned
            # when the API endpoint is not present.  We do this by setting
            # a header: "Workaround: bug1123986".
            response = HttpResponse("Not Found", status=404)
            response["Workaround"] = "bug1123986"
            return response
        stream = json_file_storage(stored_file, request)
        return HttpResponse(
            stream, mimetype='application/json; charset=utf-8',
            status=httplib.OK)

    @operation(idempotent=False)
    def delete(self, request, filename):
        """Delete a FileStorage object."""
        stored_file = get_object_or_404(
            FileStorage, filename=filename, owner=request.user)
        stored_file.delete()
        return rc.DELETED

    @classmethod
    def resource_uri(cls, stored_file=None):
        filename = "filename"
        if stored_file is not None:
            filename = stored_file.filename
        return ('file_handler', (filename, ))


class FilesHandler(OperationsHandler):
    """Manage the collection of all the files in this MAAS."""
    api_doc_section_name = "Files"
    create = read = update = delete = None
    anonymous = AnonFilesHandler

    get_by_name = operation(
        idempotent=True, exported_as='get')(get_file_by_name)
    get_by_key = operation(
        idempotent=True, exported_as='get_by_key')(get_file_by_key)

    @operation(idempotent=False)
    def add(self, request):
        """Add a new file to the file storage.

        :param filename: The file name to use in the storage.
        :type filename: string
        :param file: Actual file data with content type
            application/octet-stream

        Returns 400 if any of these conditions apply:
         - The filename is missing from the parameters
         - The file data is missing
         - More than one file is supplied
        """
        filename = request.data.get("filename", None)
        if not filename:
            raise MAASAPIBadRequest("Filename not supplied")
        files = request.FILES
        if not files:
            raise MAASAPIBadRequest("File not supplied")
        if len(files) != 1:
            raise MAASAPIBadRequest("Exactly one file must be supplied")
        uploaded_file = files['file']

        # As per the comment in FileStorage, this ought to deal in
        # chunks instead of reading the file into memory, but large
        # files are not expected.
        FileStorage.objects.save_file(filename, uploaded_file, request.user)
        return HttpResponse('', status=httplib.CREATED)

    @operation(idempotent=True)
    def list(self, request):
        """List the files from the file storage.

        The returned files are ordered by file name and the content is
        excluded.

        :param prefix: Optional prefix used to filter out the returned files.
        :type prefix: string
        """
        prefix = request.GET.get("prefix", None)
        files = FileStorage.objects.filter(owner=request.user)
        if prefix is not None:
            files = files.filter(filename__startswith=prefix)
        files = files.order_by('filename')
        return files

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('files_handler', [])
