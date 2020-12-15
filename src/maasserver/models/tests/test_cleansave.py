# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `CleanSave`."""


from unittest.mock import sentinel

from django.db.models import Model

from maasserver.models.cleansave import CleanSaveModelState
from maasserver.monkey import DeferredValueAccessError
from maasserver.testing.testcase import MAASLegacyServerTestCase
from maasserver.tests.models import CleanSaveTestModel, GenericTestModel
from maastesting.matchers import MockCalledOnceWith, MockNotCalled


class TestCleanSave(MAASLegacyServerTestCase):
    """Tests for the `CleanSave` mixin."""

    def test_state_is_clean_save_based(self):
        obj = CleanSaveTestModel.objects.create()
        self.assertIsInstance(obj._state, CleanSaveModelState)
        self.assertEqual({}, obj._state._changed_fields)

    def test_setting_property(self):
        obj = CleanSaveModelState()
        obj.test_prop = sentinel.value
        self.assertEqual(sentinel.value, obj.test_prop)

    def test_handling_deferred_field_getting(self):
        obj = CleanSaveTestModel.objects.create()
        obj = CleanSaveTestModel.objects.filter(id=obj.id).only("id").first()
        self.assertRaises(DeferredValueAccessError, lambda: obj.field)

    def test_handling_deferred_field_setting(self):
        obj = CleanSaveTestModel.objects.create()
        obj = CleanSaveTestModel.objects.filter(id=obj.id).only("id").first()
        obj.field = "test"
        self.assertIn("field", obj._state._changed_fields)
        obj.save()

    def test_field_marked_changed_for_new_obj(self):
        obj = CleanSaveTestModel()
        obj.field = "test"
        self.assertEqual({"field": None}, obj._state._changed_fields)

    def test_field_marked_changed_for_new_obj_when_reset(self):
        obj = CleanSaveTestModel()
        obj.field = "test"
        obj.field = None
        self.assertEqual({"field": None}, obj._state._changed_fields)

    def test_field_marked_changed_for_existing_obj(self):
        obj = CleanSaveTestModel.objects.create()
        obj.field = "test"
        self.assertEqual({"field": None}, obj._state._changed_fields)

    def test_field_not_marked_changed_for_existing_obj_when_reset(self):
        obj = CleanSaveTestModel.objects.create()
        obj.field = "test"
        obj.field = None
        self.assertEqual({}, obj._state._changed_fields)

    def test_field_not_marked_changed_when_refresh_from_db(self):
        obj = CleanSaveTestModel.objects.create()
        duplicate = CleanSaveTestModel.objects.get(id=obj.id)
        duplicate.field = "test"
        duplicate.save()

        obj.refresh_from_db()
        self.assertEqual("test", obj.field)
        self.assertEqual({}, obj._state._changed_fields)

    def test_field_not_marked_changed_when_refresh_from_db_no_fields(self):
        obj = CleanSaveTestModel.objects.create()
        duplicate = CleanSaveTestModel.objects.get(id=obj.id)
        duplicate.field = "test"
        duplicate.save()

        obj.refresh_from_db(fields=[])
        self.assertEqual(None, obj.field)
        self.assertEqual({}, obj._state._changed_fields)

    def test_field_not_marked_changed_when_refresh_with_changed_fields(self):
        obj = CleanSaveTestModel.objects.create()
        duplicate = CleanSaveTestModel.objects.get(id=obj.id)
        duplicate.field = "test"
        duplicate.save()

        obj.refresh_from_db(fields=["field"])
        self.assertEqual("test", obj.field)
        self.assertEqual({}, obj._state._changed_fields)

    def test_field_not_marked_changed_when_refresh_with_same_fields(self):
        obj = CleanSaveTestModel.objects.create()

        obj.refresh_from_db(fields=["field"])
        self.assertEqual(None, obj.field)
        self.assertEqual({}, obj._state._changed_fields)

    def test_field_marked_changed_when_refresh_from_db_with_no_fields(self):
        obj = CleanSaveTestModel.objects.create()
        duplicate = CleanSaveTestModel.objects.get(id=obj.id)
        duplicate.field = "test"
        duplicate.save()

        obj.field = "test"
        obj.refresh_from_db(fields=[])
        self.assertEqual("test", obj.field)
        self.assertEqual({"field": None}, obj._state._changed_fields)

    def test_field_marked_changed_rel_id_for_new_obj(self):
        related = GenericTestModel.objects.create(field="")
        obj = CleanSaveTestModel()
        obj.related_id = related.id
        self.assertEqual({"related_id": None}, obj._state._changed_fields)

    def test_field_marked_changed_rel_attname_for_new_obj(self):
        related = GenericTestModel.objects.create(field="")
        obj = CleanSaveTestModel()
        obj.related = related
        self.assertEqual({"related_id": None}, obj._state._changed_fields)

    def test_field_marked_changed_rel_id_for_existing_obj(self):
        related = GenericTestModel.objects.create(field="")
        new_related = GenericTestModel.objects.create(field="")
        obj = CleanSaveTestModel.objects.create(related=related)
        obj.related_id = new_related.id
        self.assertEqual(
            {"related_id": related.id}, obj._state._changed_fields
        )

    def test_field_marked_changed_rel_attname_for_existing_obj(self):
        related = GenericTestModel.objects.create(field="")
        new_related = GenericTestModel.objects.create(field="")
        obj = CleanSaveTestModel.objects.create(related=related)
        obj.related = new_related
        self.assertEqual(
            {"related_id": related.id}, obj._state._changed_fields
        )

    def test_field_not_marked_changed_rel_id_for_existing_obj(self):
        related = GenericTestModel.objects.create(field="")
        new_related = GenericTestModel.objects.create(field="")
        obj = CleanSaveTestModel.objects.create(related=related)
        obj.related_id = new_related.id
        obj.related_id = related.id
        self.assertEqual({}, obj._state._changed_fields)

    def test_field_not_marked_changed_rel_attname_for_existing_obj(self):
        related = GenericTestModel.objects.create(field="")
        new_related = GenericTestModel.objects.create(field="")
        obj = CleanSaveTestModel.objects.create(related=related)
        obj.related = new_related
        obj.related = related
        self.assertEqual({}, obj._state._changed_fields)

    def test_save_always_calls_save_when_new(self):
        mock_save = self.patch(Model, "save")
        obj = CleanSaveTestModel()
        obj.save()
        self.assertThat(mock_save, MockCalledOnceWith())

    def test_save_doesnt_clean_pk_and_related_fields_when_new(self):
        obj = CleanSaveTestModel()
        mock_full_clean = self.patch(obj, "full_clean")
        obj.save()
        self.assertThat(
            mock_full_clean,
            MockCalledOnceWith(
                exclude={"id", "related"}, validate_unique=False
            ),
        )

    def test_save_validates_unique_except_for_pk_when_new(self):
        obj = CleanSaveTestModel()
        mock_validate_unique = self.patch(obj, "validate_unique")
        obj.save()
        self.assertThat(
            mock_validate_unique, MockCalledOnceWith(exclude=["id"])
        )

    def test_save_resets_changed_fields_when_new(self):
        obj = CleanSaveTestModel()
        obj.field = "test"
        obj.save()
        self.assertEqual({}, obj._state._changed_fields)

    def test_save_performed_with_force_update(self):
        obj = CleanSaveTestModel.objects.create()
        mock_save = self.patch(Model, "save")
        obj.save(force_update=True)
        self.assertThat(mock_save, MockCalledOnceWith(force_update=True))

    def test_save_performed_when_id_reset(self):
        obj = CleanSaveTestModel.objects.create()
        obj.id = None
        mock_save = self.patch(Model, "save")
        obj.save()
        self.assertThat(mock_save, MockCalledOnceWith())

    def test_save_performed_when_state_forced(self):
        obj = CleanSaveTestModel.objects.create()
        obj._state.adding = True
        mock_save = self.patch(Model, "save")
        obj.save()
        self.assertThat(mock_save, MockCalledOnceWith())

    def test_save_performed_with_force_insert(self):
        obj = CleanSaveTestModel.objects.create()
        mock_save = self.patch(Model, "save")
        obj.save(force_insert=True)
        self.assertThat(mock_save, MockCalledOnceWith(force_insert=True))

    def test_save_not_performed_when_nothing_changed(self):
        obj = CleanSaveTestModel.objects.create()
        mock_save = self.patch(Model, "save")
        obj.save()
        self.assertThat(mock_save, MockNotCalled())

    def test_save_table_called_when_changed_fields(self):
        related = GenericTestModel.objects.create(field="")
        obj = CleanSaveTestModel.objects.create()
        mock_save = self.patch(Model, "_save_table")
        obj.field = "test"
        obj.related = related
        obj.save()
        self.assertThat(
            mock_save,
            MockCalledOnceWith(
                cls=CleanSaveTestModel,
                force_insert=False,
                force_update=False,
                raw=False,
                update_fields={"field", "related_id"},
                using="default",
            ),
        )
        self.assertEqual({}, obj._state._changed_fields)

    def test_save_table_updates_update_fields_with_changed_fields(self):
        related = GenericTestModel.objects.create(field="")
        obj = CleanSaveTestModel.objects.create()
        mock_save = self.patch(Model, "_save_table")
        obj.field = "test"
        obj.related = related
        obj.save(update_fields=["field"])
        self.assertThat(
            mock_save,
            MockCalledOnceWith(
                cls=CleanSaveTestModel,
                force_insert=False,
                force_update=False,
                raw=False,
                update_fields={"field", "related_id"},
                using="default",
            ),
        )
        self.assertEqual({}, obj._state._changed_fields)

    def test_save_ignores_clean_on_deferred(self):
        obj = CleanSaveTestModel.objects.create(field="test")
        obj = CleanSaveTestModel.objects.filter(id=obj.id).only("id").first()
        related = GenericTestModel.objects.create(field="")
        obj.related = related
        obj.save(force_update=True)

    def test_full_clean_excludes_unchanged_fields(self):
        related = GenericTestModel.objects.create(field="")
        obj = CleanSaveTestModel.objects.create()
        mock_full_clean = self.patch(Model, "full_clean")
        obj.related = related
        obj.save()
        self.assertThat(
            mock_full_clean,
            MockCalledOnceWith(
                exclude={"id", "field", "related"}, validate_unique=False
            ),
        )

    def test_full_clean_doesnt_exclude_changed_fields(self):
        related = GenericTestModel.objects.create(field="")
        obj = CleanSaveTestModel.objects.create()
        mock_full_clean = self.patch(Model, "full_clean")
        obj.field = "test"
        obj.related = related
        obj.save()
        self.assertThat(
            mock_full_clean,
            MockCalledOnceWith(
                exclude={"id", "related"}, validate_unique=False
            ),
        )

    def test_validate_unique_excludes_unchanged_fields(self):
        related = GenericTestModel.objects.create(field="")
        obj = CleanSaveTestModel.objects.create()
        mock_validate_unique = self.patch(Model, "validate_unique")
        obj.related = related
        obj.save()
        self.assertThat(
            mock_validate_unique, MockCalledOnceWith(exclude={"id", "field"})
        )

    def test_utils_get_changed(self):
        obj = CleanSaveTestModel.objects.create()
        obj.field = "test"
        self.assertEqual({"field"}, obj._state.get_changed())

    def test_utils_has_changed_True(self):
        obj = CleanSaveTestModel.objects.create()
        obj.field = "test"
        self.assertTrue(obj._state.has_changed("field"))

    def test_utils_has_changed_False(self):
        obj = CleanSaveTestModel.objects.create()
        self.assertFalse(obj._state.has_changed("field"))

    def test_utils_has_any_changed_True(self):
        obj = CleanSaveTestModel.objects.create()
        obj.field = "test"
        self.assertTrue(obj._state.has_any_changed(["field"]))

    def test_utils_has_any_changed_False(self):
        obj = CleanSaveTestModel.objects.create()
        self.assertFalse(obj._state.has_any_changed(["field"]))

    def test_utils_get_old_value(self):
        related = GenericTestModel.objects.create(field="")
        new_related = GenericTestModel.objects.create(field="")
        obj = CleanSaveTestModel.objects.create(related=related)
        obj.related = new_related
        self.assertEqual(related.id, obj._state.get_old_value("related_id"))

    def test_utils_get_old_value_returns_None_when_not_changed(self):
        obj = CleanSaveTestModel.objects.create()
        self.assertIsNone(obj._state.get_old_value("field"))
