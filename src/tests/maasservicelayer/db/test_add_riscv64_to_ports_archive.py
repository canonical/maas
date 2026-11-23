# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from importlib import import_module

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest

from maasserver.models import PackageRepository
from maasserver.sqlalchemy import get_sqlalchemy_django_connection

migration = import_module(
    "maasservicelayer.db.alembic.versions.0047_add_riscv64_to_ports_archive"
)


def upgrade():
    connection = get_sqlalchemy_django_connection()
    with Operations.context(MigrationContext.configure(connection)):
        migration.upgrade()


def get_ports_archive():
    return PackageRepository.objects.get(name="ports_archive", default=True)


@pytest.mark.usefixtures("maasdb")
class TestAddRiscv64ToPortsArchive:
    def test_stale_default_ports_archive_gains_riscv64(self):
        PackageRepository.objects.filter(name="ports_archive").update(
            arches=["armhf", "arm64", "ppc64el", "s390x"]
        )

        upgrade()

        assert set(get_ports_archive().arches) == {
            "armhf",
            "arm64",
            "ppc64el",
            "riscv64",
            "s390x",
        }

    def test_migration_is_idempotent(self):
        PackageRepository.objects.filter(name="ports_archive").update(
            arches=["armhf", "arm64", "ppc64el", "s390x"]
        )

        upgrade()
        upgrade()

        assert sorted(get_ports_archive().arches) == [
            "arm64",
            "armhf",
            "ppc64el",
            "riscv64",
            "s390x",
        ]

    def test_null_arches_is_reset_to_complete_default_ports_arches(self):
        PackageRepository.objects.filter(name="ports_archive").update(
            arches=None
        )

        upgrade()

        assert set(get_ports_archive().arches) == set(
            PackageRepository.PORTS_ARCHES
        )

    def test_empty_arches_is_reset_to_complete_default_ports_arches(self):
        PackageRepository.objects.filter(name="ports_archive").update(
            arches=[]
        )

        upgrade()

        assert set(get_ports_archive().arches) == set(
            PackageRepository.PORTS_ARCHES
        )

    def test_customized_arches_are_preserved(self):
        PackageRepository.objects.filter(name="ports_archive").update(
            arches=["arm64", "s390x"]
        )

        upgrade()

        assert sorted(get_ports_archive().arches) == [
            "arm64",
            "riscv64",
            "s390x",
        ]

    def test_non_default_repositories_are_untouched(self, factory):
        custom = factory.make_PackageRepository(
            name="custom-ports",
            default=False,
            arches=["arm64"],
        )

        upgrade()

        custom.refresh_from_db()
        assert custom.arches == ["arm64"]
