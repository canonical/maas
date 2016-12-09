# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = [
    "PackageRepositoryHandler",
    "PackageRepositoriesHandler",
    ]

from maasserver.api.support import (
    admin_method,
    OperationsHandler,
)
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms_packagerepository import PackageRepositoryForm
from maasserver.models import PackageRepository
from piston3.utils import rc


DISPLAYED_PACKAGE_REPOSITORY_FIELDS = (
    'id',
    'name',
    'url',
    'distributions',
    'disabled_pockets',
    'components',
    'arches',
    'key',
    'enabled',
)


class PackageRepositoryHandler(OperationsHandler):
    """Manage an individual Package Repository.

    The Package Repository is identified by its id.
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
        return ('package_repository_handler', (package_repository_id,))

    def read(self, request, package_repository_id):
        """Read Package Repository.

        Returns 404 if the repository is not found.
        """
        return PackageRepository.objects.get_object_or_404(
            package_repository_id)

    @admin_method
    def update(self, request, package_repository_id):
        """Update a Package Repository.

        :param name: The name of the Package Repository.
        :type name: unicode

        :param url: The url of the Package Repository.
        :type url: unicode

        :param distributions: Which package distributions to include.
        :type distributions: unicode

        :param disabled_pockets: The list of pockets to disable.

        :param components: The list of components to enable.

        :param arches: The list of supported architectures.

        :param key: The authentication key to use with the repository.
        :type key: unicode

        :param enabled: Whether or not the repository is enabled.
        :type enabled: boolean

        Returns 404 if the Package Repository is not found.
        """
        package_repository = PackageRepository.objects.get_object_or_404(
            package_repository_id)
        form = PackageRepositoryForm(
            instance=package_repository, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @admin_method
    def delete(self, request, package_repository_id):
        """Delete a Package Repository.

        Returns 404 if the Package Repository is not found.
        """
        package_repository = PackageRepository.objects.get_object_or_404(
            package_repository_id)
        package_repository.delete()
        return rc.DELETED


class PackageRepositoriesHandler(OperationsHandler):
    """Manage the collection of all Package Repositories in MAAS."""
    api_doc_section_name = "Package Repositories"
    update = delete = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('package_repositories_handler', [])

    def read(self, request):
        """List all Package Repositories."""
        return PackageRepository.objects.all()

    @admin_method
    def create(Self, request):
        """Create a Package Repository.

        :param name: The name of the Package Repository.
        :type name: unicode

        :param url: The url of the Package Repository.
        :type url: unicode

        :param distributions: Which package distributions to include.
        :type distributions: unicode

        :param disabled_pockets: The list of pockets to disable.

        :param components: The list of components to enable.

        :param arches: The list of supported architectures.

        :param key: The authentication key to use with the repository.
        :type key: unicode

        :param enabled: Whether or not the repository is enabled.
        :type enabled: boolean
        """
        form = PackageRepositoryForm(data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)
