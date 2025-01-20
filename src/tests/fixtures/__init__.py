#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from pathlib import Path


def get_test_data_file(filename: str) -> str:
    test_data_path = Path(__file__).parent / "test_data" / filename
    with open(test_data_path, "r") as f:
        return f.read()
