# Copyright 2018-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.db.models import Model

from maasserver.testing.testcase import MAASLegacyServerTestCase
from maasserver.tests.models import CleanSaveTestModel


class TestCleanSave(MAASLegacyServerTestCase):
    def test_save_doesnt_clean_pk_and_related_fields_when_new(self):
        obj = CleanSaveTestModel()
        mock_full_clean = self.patch(obj, "full_clean")
        obj.save()
        if hasattr(obj, "validate_constraints"):
            mock_full_clean.assert_called_once_with(
                exclude={"id", "related"},
                validate_unique=False,
                validate_constraints=False,
            )
        else:
            # FIXME Remove this once Django3 support is dropped
            mock_full_clean.assert_called_once_with(
                exclude={"id", "related"}, validate_unique=False
            )

    def test_save_validates_unique_except_for_pk_when_new(self):
        obj = CleanSaveTestModel()
        mock_validate_unique = self.patch(obj, "validate_unique")
        obj.save()
        mock_validate_unique.assert_called_once_with(exclude={"id"})

    def test_save_performed_with_force_update(self):
        obj = CleanSaveTestModel.objects.create()
        mock_save = self.patch(Model, "save")
        obj.save(force_update=True)
        mock_save.assert_called_once_with(force_update=True)

    def test_save_performed_when_id_reset(self):
        obj = CleanSaveTestModel.objects.create()
        obj.id = None
        mock_save = self.patch(Model, "save")
        obj.save()
        mock_save.assert_called_once_with()

    def test_save_performed_when_state_forced(self):
        obj = CleanSaveTestModel.objects.create()
        obj._state.adding = True
        mock_save = self.patch(Model, "save")
        obj.save()
        mock_save.assert_called_once_with()

    def test_save_performed_with_force_insert(self):
        obj = CleanSaveTestModel.objects.create()
        mock_save = self.patch(Model, "save")
        obj.save(force_insert=True)
        mock_save.assert_called_once_with(force_insert=True)
