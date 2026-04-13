# Copyright 2014-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from twisted.application.internet import TimerService
from twisted.internet.defer import fail

from maasserver import bootresources
from maasserver.components import (
    get_persistent_error,
    register_persistent_error,
)
from maasserver.enum import COMPONENT
from maasserver.testing.config import RegionConfigurationFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maastesting import get_testing_timeout
from maastesting.crochet import wait_for
from maastesting.twisted import TwistedLoggerFixture
from provisioningserver.utils.text import normalise_whitespace
from provisioningserver.utils.twisted import asynchronous

TIMEOUT = get_testing_timeout()
wait_for_reactor = wait_for()


class TestStopImportResources(MAASTransactionServerTestCase):
    def test_does_nothing_if_import_not_running(self):
        mock_running = self.patch(bootresources, "is_import_resources_running")
        mock_running.return_value = False
        mock_cancel_workflow = self.patch(bootresources, "cancel_workflow")
        mock_cancel_workflows_of_type = self.patch(
            bootresources, "cancel_workflows_of_type"
        )

        bootresources.stop_import_resources()

        mock_running.assert_called_once()
        mock_cancel_workflow.assert_not_called()
        mock_cancel_workflows_of_type.assert_not_called()

    def test_sends_stop_import_notification(self):
        mock_running = self.patch(bootresources, "is_import_resources_running")
        mock_running.return_value = True
        mock_cancel_workflow = self.patch(bootresources, "cancel_workflow")

        bootresources.stop_import_resources()

        mock_running.assert_called_once()
        mock_cancel_workflow.assert_called_once_with(
            workflow_id="master-image-sync"
        )

class TestImportResourcesProgressService(MAASServerTestCase):
    """Tests for `ImportResourcesProgressService`."""

    def test_is_a_TimerService(self):
        service = bootresources.ImportResourcesProgressService()
        self.assertIsInstance(service, TimerService)

    def test_runs_every_three_minutes(self):
        service = bootresources.ImportResourcesProgressService()
        self.assertEqual(180, service.step)

    def test_calls_try_check_boot_images(self):
        service = bootresources.ImportResourcesProgressService()
        func, args, kwargs = service.call
        self.assertEqual(func, service.try_check_boot_images)
        self.assertEqual(args, ())
        self.assertEqual(kwargs, {})


class TestImportResourcesProgressServiceAsync(MAASTransactionServerTestCase):
    """Tests for the async parts of `ImportResourcesProgressService`."""

    def set_maas_url(self):
        maas_url_path = "/path/%s" % factory.make_string()
        maas_url = factory.make_simple_http_url(path=maas_url_path)
        self.useFixture(RegionConfigurationFixture(maas_url=maas_url))
        return maas_url, maas_url_path

    def patch_are_functions(self, service, region_answer):
        # Patch the are_boot_images_available_* functions.
        are_region_func = self.patch_autospec(
            service, "are_boot_images_available_in_the_region"
        )
        are_region_func.return_value = region_answer

    def test_adds_warning_if_boot_image_import_not_started(self):
        maas_url, maas_url_path = self.set_maas_url()

        service = bootresources.ImportResourcesProgressService()
        self.patch_are_functions(service, False)

        check_boot_images = asynchronous(service.check_boot_images)
        check_boot_images().wait(TIMEOUT)

        error_observed = get_persistent_error(COMPONENT.IMPORT_PXE_FILES)
        error_expected = """\
        Boot image import process not started. Machines will not be able to
        provision without boot images. Visit the <a href="/MAAS/r/images">boot images</a>
        page to start the import.
        """
        self.assertEqual(
            normalise_whitespace(error_expected),
            normalise_whitespace(error_observed),
        )

    def test_removes_warning_if_boot_image_process_started(self):
        register_persistent_error(
            COMPONENT.IMPORT_PXE_FILES,
            "You rotten swine, you! You have deaded me!",
        )

        service = bootresources.ImportResourcesProgressService()
        self.patch_are_functions(service, True)

        check_boot_images = asynchronous(service.check_boot_images)
        check_boot_images().wait(TIMEOUT)

        error = get_persistent_error(COMPONENT.IMPORT_PXE_FILES)
        self.assertIsNone(error)

    def test_logs_all_errors(self):
        logger = self.useFixture(TwistedLoggerFixture())

        exception = factory.make_exception()
        service = bootresources.ImportResourcesProgressService()
        check_boot_images = self.patch_autospec(service, "check_boot_images")
        check_boot_images.return_value = fail(exception)
        try_check_boot_images = asynchronous(service.try_check_boot_images)
        try_check_boot_images().wait(TIMEOUT)

        self.assertEqual(
            [
                "Failure checking for boot images.",
                "Traceback (most recent call last):",
                f"Failure: maastesting.factory.{type(exception).__name__}: ",
            ],
            logger.output.splitlines(),
        )

    def test_are_boot_images_available_in_the_region(self):
        service = bootresources.ImportResourcesProgressService()
        self.assertFalse(service.are_boot_images_available_in_the_region())
        factory.make_BootResource()
        self.assertTrue(service.are_boot_images_available_in_the_region())
