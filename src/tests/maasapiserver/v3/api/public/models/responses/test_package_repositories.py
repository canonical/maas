# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from maasapiserver.v3.api.public.handlers.package_repositories import (
    PackageRepositoryResponse,
)
from maasservicelayer.models.fields import PackageRepoUrl
from maasservicelayer.models.package_repositories import PackageRepository
from maasservicelayer.utils.date import utcnow


class TestPackageRepositoryResponse:
    def test_from_model(self) -> None:
        package_repo = PackageRepository(
            id=1,
            created=utcnow(),
            updated=utcnow(),
            name="test-main",
            key="test-key",
            url=PackageRepoUrl("http://archive.ubuntu.com/ubuntu"),
            distributions=[],
            components=set(),
            arches=set(),
            disabled_pockets=set(),
            disabled_components=set(),
            disable_sources=False,
            default=False,
            enabled=True,
        )
        response = PackageRepositoryResponse.from_model(
            package_repository=package_repo, self_base_hyperlink="http://test/"
        )
        assert response.kind == "PackageRepository"
        assert response.name == package_repo.name
        assert response.key == package_repo.key
        assert response.url == package_repo.url
        assert response.distributions == package_repo.distributions
        assert response.components == package_repo.components
        assert response.arches == package_repo.arches
        assert response.disabled_pockets == package_repo.disabled_pockets
        assert response.disabled_components == package_repo.disabled_components
        assert response.disable_sources == package_repo.disable_sources
        assert response.enabled == package_repo.enabled
        assert response.hal_links.self.href == "http://test/1"
