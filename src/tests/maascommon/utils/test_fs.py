# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import os
from pathlib import Path
from shutil import rmtree
import stat
from unittest.mock import MagicMock, patch

import pytest

from maascommon.utils.fs import tempdir
from maastesting.factory import factory


class TestTempdir:
    def test_creates_real_fresh_directory(self) -> None:
        stored_text = factory.make_string()
        retrieved_text = ""
        filename = factory.make_name("test-file")

        with tempdir() as directory:
            assert os.path.isdir(directory)

            file_path = os.path.join(directory, filename)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(stored_text)

            with open(file_path, "r", encoding="utf-8") as f:
                retrieved_text = f.read()

            files = os.listdir(directory)

        assert stored_text == retrieved_text
        assert [filename] == files

    def test_creates_unique_directory(self) -> None:
        with tempdir() as dir1, tempdir() as dir2:
            pass
        assert not dir1 == dir2

    def test_cleans_up_on_successful_exit(self) -> None:
        with tempdir() as directory:
            file_path = factory.make_file(directory)

        assert not os.path.isdir(directory)
        assert not os.path.exists(file_path)

    def test_cleans_up_on_exception_exit(self) -> None:
        class DeliberateFailure(Exception):
            pass

        with pytest.raises(DeliberateFailure) as e:
            with tempdir() as directory:
                file_path = factory.make_file(directory)
                raise DeliberateFailure("Exiting context by exception")
            assert str(e.value) == "Exiting context by exception"

        assert not os.path.isdir(directory)
        assert not os.path.exists(file_path)

    def test_tolerates_disappearing_dir(self) -> None:
        with tempdir() as directory:
            rmtree(directory)

        assert not os.path.isdir(directory)

    def test_uses_location(self, tmp_path: Path) -> None:
        """Test tempdir uses provided location.

        This test relies on the `tmp_path` pytest fixture."""
        location_listing = []
        with tempdir(location=tmp_path) as directory:
            assert os.path.isdir(directory)
            location_listing = os.listdir(tmp_path)

        assert not tmp_path == directory
        assert directory.startswith(str(tmp_path) + os.path.sep)
        assert os.path.basename(directory) in location_listing
        assert os.path.isdir(tmp_path)
        assert not os.path.isdir(directory)

    def test_yields_unicode(self) -> None:
        with tempdir() as directory:
            pass

        assert isinstance(directory, str)

    @patch("maascommon.utils.fs.mkdtemp")
    def test_accepts_unicode_from_mkdtemp(
        self,
        mock_mkdtemp: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test tempdir accepts unicode from `mkdtemp`.

        This test relies on the `tmp_path` pytest fixture."""
        fake_dir = os.path.join(tmp_path, factory.make_name("tempdir"))
        assert isinstance(fake_dir, str)

        mock_mkdtemp.return_value = fake_dir

        with tempdir() as directory:
            pass

        assert fake_dir == directory
        assert isinstance(directory, str)

    def test_uses_prefix(self) -> None:
        prefix = factory.make_string(3)
        with tempdir(prefix=prefix) as directory:
            pass

        assert os.path.basename(directory).startswith(prefix)

    def test_uses_suffix(self) -> None:
        suffix = factory.make_string(3)
        with tempdir(suffix=suffix) as directory:
            pass

        assert os.path.basename(directory).endswith(suffix)

    def test_restricts_access(self) -> None:
        mode = 0
        with tempdir() as directory:
            mode = os.stat(directory).st_mode
        assert stat.S_IMODE(mode) == stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR
