__all__ = [
    "get_test_data_file",
]

from pathlib import Path


def get_test_data_file(filename: str) -> bytes:
    test_data_path = Path(__file__).parent / "test_data" / filename
    with open(test_data_path, "r") as f:
        return f.read()
