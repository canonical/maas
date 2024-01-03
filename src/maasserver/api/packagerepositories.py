# Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from piston3.utils import rc

from maasserver.api.support import admin_method, OperationsHandler
from maasserver.audit import create_audit_event
from maasserver.enum import ENDPOINT
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms.packagerepository import PackageRepositoryForm
from maasserver.models import PackageRepository
from provisioningserver.events import EVENT_TYPES

DISPLAYED_PACKAGE_REPOSITORY_FIELDS = (
    "id",
    "name",
    "url",
    "distributions",
    "disabled_pockets",
    "disabled_components",
    "disable_sources",
    "components",
    "arches",
    "key",
    "enabled",
)


class PackageRepositoryHandler(OperationsHandler):
    """
    Manage an individual package repository.

    A package repository is identified by its id.
    """

    api_doc_section_name = "Package Repository"
    create = None
    model = PackageRepository
    fields = DISPLAYED_PACKAGE_REPOSITORY_FIELDS

    @classmethod
    def resource_uri(cls, package_repository=None):
        # See the comment in NodeHandler.resource_uri.
        if package_repository is not None:
            package_repository_id = package_repository.id
        else:
            package_repository_id = "id"
        return ("package_repository_handler", (package_repository_id,))

    def read(self, request, id):
        """@description-title Read a package repository
        @description Read a package repository with the given id.

        @param (int) "{id}" [required=true] A package repository id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing information
        about the requested package repository.
        @success-example "success-json" [exkey=pkg-repos-read-by-id]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested package repository is not
        found.
        @error-example "not-found"
            No PackageRepository matches the given query.
        """
        return PackageRepository.objects.get_object_or_404(id)

    @admin_method
    def update(self, request, id):
        """@description-title Update a package repository
        @description Update the package repository with the given id.

        @param (int) "{id}" [required=true] A package repository id.

        @param (string) "name" [required=false] The name of the package
        repository.

        @param (string) "url" [required=false] The url of the package
        repository.

        @param (string) "distributions" [required=false] Which package
        distributions to include.

        @param (string) "disabled_pockets" [required=false] The list of pockets
        to disable.

        @param (string) "disabled_components" [required=false] The list of
        components to disable. Only applicable to the default Ubuntu
        repositories.

        @param (string) "components" [required=false] The list of components to
        enable. Only applicable to custom repositories.

        @param (string) "arches" [required=false] The list of supported
        architectures.

        @param (string) "key" [required=false] The authentication key to use
        with the repository.

        @param (boolean) "disable_sources" [required=false] Disable deb-src
        lines.

        @param (boolean) "enabled" [required=false] Whether or not the
        repository is enabled.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing information
        about the updated package repository.
        @success-example "success-json" [exkey=pkg-repos-update] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested package repository is not
        found.
        @error-example "not-found"
            No PackageRepository matches the given query.
        """
        package_repository = PackageRepository.objects.get_object_or_404(id)
        form = PackageRepositoryForm(
            instance=package_repository, data=request.data
        )
        if form.is_valid():
            return form.save(ENDPOINT.API, request)
        else:
            raise MAASAPIValidationError(form.errors)

    @admin_method
    def delete(self, request, id):
        """@description-title Delete a package repository
        @description Delete a package repository with the given id.

        @param (int) "{id}" [required=true] A package repository id.

        @success (http-status-code) "server-success" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested package repository is not
        found.
        @error-example "not-found"
            No PackageRepository matches the given query.
        """
        package_repository = PackageRepository.objects.get_object_or_404(id)
        package_repository.delete()
        create_audit_event(
            EVENT_TYPES.SETTINGS,
            ENDPOINT.API,
            request,
            None,
            description=(
                "Deleted package repository '%s'." % package_repository.name
            ),
        )
        return rc.DELETED


class PackageRepositoriesHandler(OperationsHandler):
    """Manage the collection of all Package Repositories in MAAS."""

    api_doc_section_name = "Package Repositories"
    update = delete = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("package_repositories_handler", [])

    def read(self, request):
        """@description-title List package repositories
        @description List all available package repositories.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing information
        about the updated package repository.
        @success-example "success-json" [exkey=pkg-repos-update] placeholder
        text
        """
        return PackageRepository.objects.all()

    @admin_method
    def create(self, request):
        """@description-title Create a package repository
        @description Create a new package repository.

        @param (string) "name" [required=true] The name of the package
        repository.

        @param (string) "url" [required=true] The url of the package
        repository.

        @param (string) "distributions" [required=false] Which package
        distributions to include.

        @param (string) "disabled_pockets" [required=false] The list of pockets
        to disable.

        @param (string) "disabled_components" [required=false] The list of
        components to disable. Only applicable to the default Ubuntu
        repositories.

        @param (string) "components" [required=false] The list of components to
        enable. Only applicable to custom repositories.

        @param (string) "arches" [required=false] The list of supported
        architectures.

        @param (string) "key" [required=false] The authentication key to use
        with the repository.

        @param (boolean) "disable_sources" [required=false] Disable deb-src
        lines.

        @param (boolean) "enabled" [required=false] Whether or not the
        repository is enabled.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing information
        about the new package repository.
        @success-example "success-json" [exkey=pkg-repos-update] placeholder
        text
        """
        form = PackageRepositoryForm(data=request.data)
        if form.is_valid():
            return form.save(ENDPOINT.API, request)
        else:
            raise MAASAPIValidationError(form.errors)
