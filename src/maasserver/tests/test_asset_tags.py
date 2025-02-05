import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from maasserver.templatetags.asset_tags import get_index_css_path
from maastesting.testcase import MAASTestCase


class TestGetIndexCssPath(MAASTestCase):
    def test_css_file(self):
        manifest_content = {"index.html": {"css": ["assets/index.abc123.css"]}}
        # Create temporary manifest file to make the test independent of ui
        # build.
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json"
        ) as temp_manifest:
            # Write the test manifest content
            json.dump(manifest_content, temp_manifest)
            temp_manifest.flush()

            # Patch the manifest path to point to the temp file
            with patch(
                "maasserver.djangosettings.settings.MAAS_UI_MANIFEST_PATH",
                Path(temp_manifest.name),
            ):
                css_path = get_index_css_path()
                self.assertEqual(css_path, "/MAAS/r/assets/index.abc123.css")

    def test_returns_empty_string_if_manifest_does_not_exist(self):
        nonexistent_path = Path("/nonexistent/manifest.json")

        with patch(
            "maasserver.templatetags.asset_tags.settings"
            ".MAAS_UI_MANIFEST_PATH",
            nonexistent_path,
        ):
            self.assertEqual(get_index_css_path(), "")
