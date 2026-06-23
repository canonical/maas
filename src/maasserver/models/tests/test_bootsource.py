# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `BootSource`."""

from django.core.exceptions import ValidationError

from maascommon.workflows.bootresource import (
    FETCH_MANIFEST_AND_UPDATE_CACHE_WORKFLOW_NAME,
    POST_UPDATE_BOOT_SOURCE_URL_WORKFLOW_NAME,
    PostUpdateBootSourceUrlParam,
)
import maasserver.models.bootsource as boot_source_module
from maasserver.models.bootsource import BootSource
from maasserver.models.signals import bootsources
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


def make_BootSource():
    """Return a `BootSource` with random keyring data."""
    return factory.make_BootSource(keyring_data=factory.make_bytes())


class TestBootSource(MAASServerTestCase):
    """Tests for the `BootSource` model."""

    def setUp(self):
        super().setUp()
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

    def test_valid_boot_source_is_valid(self):
        boot_source = BootSource(
            url="http://example.com", keyring_filename="/path/to/something"
        )
        boot_source.save()
        self.assertTrue(BootSource.objects.filter(id=boot_source.id).exists())

    def test_url_is_unqiue(self):
        boot_source = factory.make_BootSource()
        self.assertRaises(
            ValidationError, factory.make_BootSource, url=boot_source.url
        )

    def test_cannot_set_keyring_data_and_filename(self):
        # A BootSource cannot have both a keyring filename and keyring
        # data. Attempting to set both will raise an error.
        boot_source = BootSource(
            url="http://example.com",
            keyring_filename="/path/to/something",
            keyring_data=b"blahblahblahblah",
        )
        self.assertRaises(ValidationError, boot_source.clean)

    def test_cannot_leave_keyring_data_and_filename_unset(self):
        boot_source = BootSource(
            url="http://example.com", keyring_filename="", keyring_data=b""
        )
        self.assertRaises(ValidationError, boot_source.clean)

    def test_keyring_data_and_filename_can_be_unset_if_stream_is_unsigned(
        self,
    ):
        boot_source = BootSource(
            url="http://example.com/streams/v1/index.json",
            keyring_filename="",
            keyring_data=b"",
        )
        boot_source.save()

    def test_generate_priority_boot_source(self):
        # create a boot source
        boot_source_1 = make_BootSource()
        # Stable boot source is created with priority 1, so the next priority is 2
        assert boot_source_1.priority == 2
        # update boot source: _generate_priority() is called
        boot_source_1.url = "http://%s.com/" % factory.make_name("source-url")
        boot_source_1.save()
        # create a new boot source (max priority == 2)
        boot_source_2 = make_BootSource()
        assert boot_source_2.priority == 3
        # create a new boot source (max priority == 10)
        boot_source_1.priority = 10
        boot_source_1.save()
        boot_source_2 = make_BootSource()
        assert boot_source_2.priority == 11

    def test_generate_skip_keyring_verification(self):
        # create a boot source providing a basic URL
        boot_source_1 = make_BootSource()
        assert not boot_source_1.skip_keyring_verification
        # create a boot source using an unsigned json index
        boot_source_2 = factory.make_BootSource(
            url="https://images.maas.io/ephemeral-v3/candidate/streams/v1/index.json"
        )
        assert boot_source_2.skip_keyring_verification
        boot_source_2.skip_keyring_verification = False
        assert not boot_source_2.skip_keyring_verification
        # create a boot source using a signed json index
        boot_source_3 = factory.make_BootSource(
            url="https://images.maas.io/ephemeral-v3/candidate/streams/v1/index.sjson"
        )
        assert not boot_source_3.skip_keyring_verification

    def test_name_defaults_to_url(self):
        boot_source = BootSource(
            url="http://example.com", keyring_filename="/path/to/something"
        )
        boot_source.save()
        self.assertEqual(boot_source.name, "http://example.com")

    def test_name_is_unique(self):
        factory.make_BootSource(name="source1", url="http://foo.com")
        self.assertRaises(
            ValidationError,
            factory.make_BootSource,
            name="source1",
            url="http://bar.com",
        )

    def test_url_trailing_slash_is_stripped(self):
        boot_source = BootSource(
            url="http://example.com/path/",
            keyring_filename="/path/to/something",
        )
        boot_source.save()
        self.assertEqual(boot_source.url, "http://example.com/path")

    def test_enabled_defaults_to_true(self):
        boot_source = BootSource(
            url="http://example.com", keyring_filename="/path/to/something"
        )
        boot_source.save()
        self.assertTrue(boot_source.enabled)

    def test_verify_selection_after_url_update(self):
        mock_start_workflow = self.patch(boot_source_module, "start_workflow")
        boot_source = make_BootSource()
        boot_source.verify_selections_after_url_update()
        mock_start_workflow.assert_called_once_with(
            workflow_name=POST_UPDATE_BOOT_SOURCE_URL_WORKFLOW_NAME,
            param=PostUpdateBootSourceUrlParam(boot_source.id),
        )

    def test_refetch_manifest(self):
        mock_start_workflow = self.patch(boot_source_module, "start_workflow")
        boot_source = make_BootSource()
        boot_source.refetch_manifest()
        mock_start_workflow.assert_called_once_with(
            workflow_name=FETCH_MANIFEST_AND_UPDATE_CACHE_WORKFLOW_NAME,
            param=boot_source.id,
        )
